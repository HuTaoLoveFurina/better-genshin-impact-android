"""ADB device connection layer: wired/wireless connection, screenshot capture, and tap/swipe input.

Two run modes are supported:
  - Default (ADB mode): drives the device through the ``adb`` command on a PC (Linux / macOS / Windows).
  - ``local=True`` (rooted Android shell): runs directly inside the device's own shell, using
    ``/system/bin/screencap`` and ``/system/bin/input`` for capture/input with no adb forwarding.
    Typical use: Termux (rooted) or a Magisk terminal running ``python -m bgia.cli run --local``.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass

import cv2
import numpy as np

log = logging.getLogger(__name__)


class AdbError(RuntimeError):
    pass


@dataclass
class DisplayInfo:
    width: int
    height: int
    rotation: int  # 0/1/2/3, where 1 and 3 mean landscape


def _resolve_adb(adb_path: str) -> str:
    """Locate the adb executable in PATH or common directories, compatible with Windows (.exe) and Linux."""
    # 1) directly found in PATH
    found = shutil.which(adb_path)
    if found:
        return found

    # 2) on Windows, retry once with the .exe suffix appended
    if sys.platform.startswith("win"):
        if not adb_path.lower().endswith(".exe"):
            found = shutil.which(adb_path + ".exe")
            if found:
                return found
        # common locations: current dir / platform-tools / user home
        candidates = [
            adb_path,
            adb_path + ".exe",
            "platform-tools/adb.exe",
            "platform-tools/adb",
            "adb.exe",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk", "platform-tools", "adb.exe"),
            os.path.join(os.path.expanduser("~"), "Android", "Sdk", "platform-tools", "adb.exe"),
        ]
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        return adb_path  # if not found, return as-is and let the caller raise a clearer error
    return adb_path


def _resolve_local_bin(name: str) -> str:
    """In rooted-Android local mode, locate a system binary (screencap / input, etc.).

Prefer PATH (usually present in Termux-like environments); otherwise fall back to common system paths.
    """
    found = shutil.which(name)
    if found:
        return found
    for p in ("/system/bin/" + name, "/system/xbin/" + name, "/sbin/" + name):
        if os.path.isfile(p):
            return p
    return name


class AdbDevice:
    """Wrapper around a single device's adb / local operations.

Screenshots go through the ``exec-out screencap`` binary pipe by default to avoid the shell's CRLF conversion.
On some older devices that pipe is unstable, in which case it auto-degrades to ``screencap -p`` + newline repair.

When ``local=True``, all commands run directly on the local (rooted Android) shell:
  - screenshot: ``screencap -p`` writes PNG to stdout
  - tap: ``input tap x y``
  - no ``adb`` prefix or serial needed.
    """

    def __init__(
        self,
        serial: str | None = None,
        adb_path: str = "adb",
        screencap_timeout: float = 10.0,
        local: bool = False,
    ):
        self.local = local
        self.adb_path = _resolve_adb(adb_path) if not local else adb_path
        # In local mode, cache the resolved system-binary paths
        self._screencap_bin = _resolve_local_bin("screencap") if local else ""
        self._input_bin = _resolve_local_bin("input") if local else ""
        self.serial = serial or ("local" if local else None)
        self.screencap_timeout = screencap_timeout
        self._use_raw_screencap = not local  # local mode uses PNG only
        self._display: DisplayInfo | None = None
        # Physical pixel size of the most recent screenshot (physical pixels; raw screencap returns real display resolution)
        self._frame_w: int | None = None
        self._frame_h: int | None = None

    # ------------------------------------------------------------------ Basics

    def _base_cmd(self) -> list[str]:
        if self.local:
            return []
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def run(self, *args: str, timeout: float = 15.0, binary: bool = False):
        """Run a command. Returns raw bytes when binary=True.

In local mode, args are the local commands to execute (e.g. "screencap", "-p").
        """
        if self.local:
            try:
                proc = subprocess.run(list(args), capture_output=True, timeout=timeout, check=False)
            except subprocess.TimeoutExpired as exc:
                raise AdbError(f"command timed out: {' '.join(args)}") from exc
            except FileNotFoundError as exc:
                raise AdbError(f"local command not found: {' '.join(args)} (make sure this runs inside a rooted shell)") from exc
            if proc.returncode != 0:
                err = proc.stderr.decode("utf-8", "ignore").strip()
                raise AdbError(f"command failed ({proc.returncode}): {' '.join(args)}\n{err}")
            return proc.stdout if binary else proc.stdout.decode("utf-8", "ignore")

        cmd = self._base_cmd() + list(args)
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb command timed out: {' '.join(args)}") from exc
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "ignore").strip()
            raise AdbError(f"adb command failed ({proc.returncode}): {' '.join(args)}\n{err}")
        return proc.stdout if binary else proc.stdout.decode("utf-8", "ignore")

    def shell(self, command: str, timeout: float = 15.0) -> str:
        if self.local:
            # In local mode, run the command via the shell directly (equivalent to `adb shell`)
            try:
                proc = subprocess.run(
                    ["sh", "-c", command], capture_output=True, timeout=timeout, check=False
                )
            except FileNotFoundError as exc:
                raise AdbError(f"sh not found: {exc}") from exc
            return proc.stdout.decode("utf-8", "ignore").strip()
        return self.run("shell", command, timeout=timeout).strip()

    # ------------------------------------------------------------------ Connection

    @classmethod
    def list_devices(cls, adb_path: str = "adb", local: bool = False) -> list[tuple[str, str]]:
        """Return [(serial, state), ...]."""
        if local:
            # Local mode: self-check whether the environment has root-shell capability
            if shutil.which("screencap") or os.path.isfile("/system/bin/screencap"):
                return [("local", "device")]
            return []
        exe = _resolve_adb(adb_path)
        try:
            out = subprocess.run([exe, "devices"], capture_output=True, timeout=15, check=False)
        except FileNotFoundError as exc:
            raise AdbError(f"adb executable not found: {adb_path}; install Android Platform Tools") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError("adb devices timed out") from exc
        devices = []
        for line in out.stdout.decode("utf-8", "ignore").splitlines()[1:]:
            line = line.strip()
            if not line or "\t" not in line:
                continue
            serial, state = line.split("\t", 1)
            devices.append((serial.strip(), state.strip()))
        return devices

    @classmethod
    def connect_wireless(cls, address: str, adb_path: str = "adb", timeout: float = 20.0) -> str:
        """Connect a wireless device; address looks like 192.168.1.10:5555. Returns the normalized serial."""
        exe = shutil.which(adb_path) or adb_path
        if ":" not in address:
            address = f"{address}:5555"
        proc = subprocess.run([exe, "connect", address], capture_output=True, timeout=timeout, check=False)
        msg = proc.stdout.decode("utf-8", "ignore").strip()
        if "connected" not in msg.lower() or "cannot" in msg.lower() or "failed" in msg.lower():
            raise AdbError(f"wireless connection failed: {msg}")
        log.info("wireless connection established: %s", msg)
        return address

    def wait_ready(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            for serial, state in self.list_devices(self.adb_path):
                if (self.serial is None or serial == self.serial) and state == "device":
                    if self.serial is None:
                        self.serial = serial
                    return
            time.sleep(1.0)
        raise AdbError("timed out waiting for the device to be ready; check USB debugging authorization or wireless connection")

    # ------------------------------------------------------------------ Screen

    def get_display(self, refresh: bool = False) -> DisplayInfo:
        if self._display is not None and not refresh:
            return self._display

        size_out = self.shell("wm size")
        # Prefer the Override size (some devices have their resolution changed by an app)
        m = re.search(r"Override size:\s*(\d+)x(\d+)", size_out) or re.search(
            r"Physical size:\s*(\d+)x(\d+)", size_out
        )
        if not m:
            raise AdbError(f"cannot parse screen size: {size_out}")
        w, h = int(m.group(1)), int(m.group(2))

        rot_out = self.shell("dumpsys input | grep -m 1 SurfaceOrientation") or ""
        rm = re.search(r"SurfaceOrientation:\s*(\d)", rot_out)
        if not rm:
            rot_out = self.shell("dumpsys display | grep -m 1 -o 'orientation=[0-9]'") or ""
            rm = re.search(r"orientation=(\d)", rot_out)
        rotation = int(rm.group(1)) if rm else 0

        # `wm size` reports the portrait baseline; swap when in landscape
        if rotation in (1, 3) and h > w:
            w, h = h, w

        self._display = DisplayInfo(width=w, height=h, rotation=rotation)
        log.debug("display info: %s", self._display)
        return self._display

    def screencap(self) -> np.ndarray:
        """Capture the current screen and return a BGR ndarray.

Also caches the screenshot's physical size for DPI/scale-adaptive coordinate conversion in tap/swipe.
        """
        if self.local:
            # Local mode: `screencap -p` writes PNG directly to stdout
            data = self.run(self._screencap_bin, "-p", timeout=self.screencap_timeout, binary=True)
            img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise AdbError("local screenshot decode failed (confirm screencap is available and authorized)")
            self._frame_w, self._frame_h = img.shape[1], img.shape[0]
            return img

        if self._use_raw_screencap:
            try:
                img = self._screencap_raw()
                self._frame_w, self._frame_h = img.shape[1], img.shape[0]
                return img
            except AdbError as exc:
                log.warning("raw screencap failed, degrading to PNG mode: %s", exc)
                self._use_raw_screencap = False
        img = self._screencap_png()
        self._frame_w, self._frame_h = img.shape[1], img.shape[0]
        return img

    def _to_input_coords(self, x: float, y: float) -> tuple[float, float]:
        """Convert a screenshot physical-pixel coordinate into the logical coordinate expected by ``input tap/swipe``.

Background: ``screencap`` produces the real display resolution (physical pixels), while Android's
``input tap`` uses the logical resolution reported by ``wm size``. When the device has a modified DPI,
``wm density``, or a ``wm size`` Override (common for game scaling), there is a ratio difference
``ratio = physical_width / logical_width``; tapping with the raw screenshot coordinates would drift
systematically. This compensates automatically using the cached frame and display sizes.
        """
        if self._frame_w and self._display and self._display.width:
            ratio = self._frame_w / self._display.width
            if abs(ratio - 1.0) > 1e-3:
                return x / ratio, y / ratio
        return x, y

    def _screencap_raw(self) -> np.ndarray:
        """When called without args, screencap outputs raw pixels with a header of w/h/format(/colorspace)."""
        data = self.run("exec-out", "screencap", timeout=self.screencap_timeout, binary=True)
        if len(data) < 16:
            raise AdbError("screencap returned data too short")

        w, h, fmt = np.frombuffer(data[:12], dtype="<u4")
        # Android 9+ has an extra 4-byte colorspace field in the header
        for header in (16, 12):
            expected = int(w) * int(h) * 4
            if len(data) - header == expected:
                buf = np.frombuffer(data[header : header + expected], dtype=np.uint8)
                img = buf.reshape(int(h), int(w), 4)
                if int(fmt) == 1:  # RGBA_8888
                    return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        raise AdbError(f"screencap size mismatch: w={w} h={h} len={len(data)}")

    def _screencap_png(self) -> np.ndarray:
        data = self.run("exec-out", "screencap", "-p", timeout=self.screencap_timeout, binary=True)
        if b"\r\n" in data[:64] and not data.startswith(b"\x89PNG"):
            data = data.replace(b"\r\n", b"\n")
        img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise AdbError("PNG screenshot decode failed")
        return img

    # ------------------------------------------------------------------ Input

    def tap(self, x: int, y: int) -> None:
        # Screenshot physical coords -> input logical coords (DPI/scale adaptive)
        ix, iy = self._to_input_coords(x, y)
        if self.local:
            self.run(self._input_bin, "tap", str(int(round(ix))), str(int(round(iy))))
        else:
            self.shell(f"input tap {int(round(ix))} {int(round(iy))}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        # Screenshot physical coords -> input logical coords (DPI/scale adaptive)
        ix1, iy1 = self._to_input_coords(x1, y1)
        ix2, iy2 = self._to_input_coords(x2, y2)
        if self.local:
            self.run(
                self._input_bin, "swipe",
                str(int(round(ix1))), str(int(round(iy1))),
                str(int(round(ix2))), str(int(round(iy2))), str(int(duration_ms)),
            )
        else:
            self.shell(
                f"input swipe {int(round(ix1))} {int(round(iy1))} "
                f"{int(round(ix2))} {int(round(iy2))} {int(duration_ms)}"
            )

    def key(self, keycode: str | int) -> None:
        if self.local:
            self.run(self._input_bin, "keyevent", str(keycode))
        else:
            self.shell(f"input keyevent {keycode}")

    # ------------------------------------------------------------------ apps

    def current_focus(self) -> str:
        out = self.shell("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        if not out:
            out = self.shell("dumpsys activity activities | grep -m 1 ResumedActivity")
        return out

    def is_package_running(self, package: str) -> bool:
        return bool(self.shell(f"pidof {package}"))

    def start_app(self, package: str) -> None:
        self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
