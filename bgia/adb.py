"""ADB 设备连接层：负责有线/无线连接、截图、模拟点击。

支持两种运行模式：
  - 默认（ADB 模式）：通过 PC 上的 ``adb`` 命令连接设备（Linux / macOS / Windows）。
  - ``local=True``（已 root 的 Android shell）：直接在安卓设备自身的 shell 中运行，
    截图/点击走 ``/system/bin/screencap`` 与 ``/system/bin/input``，无需 adb 转发。
    典型场景：Termux（已 root）或 Magisk 终端中 ``python -m bgia.cli run --local``。
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
    rotation: int  # 0/1/2/3，1 和 3 为横屏


def _resolve_adb(adb_path: str) -> str:
    """在 PATH 或常见目录中定位 adb 可执行文件，兼容 Windows (.exe) 与 Linux。"""
    # 1) PATH 中直接可找到
    found = shutil.which(adb_path)
    if found:
        return found

    # 2) Windows 上补全 .exe 后缀再试一次
    if sys.platform.startswith("win"):
        if not adb_path.lower().endswith(".exe"):
            found = shutil.which(adb_path + ".exe")
            if found:
                return found
        # 常见位置：当前目录 / platform-tools / 用户目录
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
        return adb_path  # 找不到则原样返回，交给上层报更清晰的错误
    return adb_path


def _resolve_local_bin(name: str) -> str:
    """已 root 安卓本地模式下，定位系统二进制（screencap / input 等）。

    优先使用 PATH（Termux 等环境通常已包含），否则回退到常见的系统路径。
    """
    found = shutil.which(name)
    if found:
        return found
    for p in ("/system/bin/" + name, "/system/xbin/" + name, "/sbin/" + name):
        if os.path.isfile(p):
            return p
    return name


class AdbDevice:
    """封装单台设备的 adb / 本地操作。

    截图默认走 ``exec-out screencap`` 二进制管道，避免 shell 的 CRLF 转换问题。
    在部分老设备上该管道不稳定，此时自动降级为 ``screencap -p`` + 换行修复。

    当 ``local=True`` 时所有命令直接在本地（已 root 的安卓 shell）执行：
      - 截图：``screencap -p`` 输出 PNG 到 stdout
      - 点击：``input tap x y``
      - 无需 ``adb`` 前缀与序列号。
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
        # 本地模式下缓存系统二进制路径
        self._screencap_bin = _resolve_local_bin("screencap") if local else ""
        self._input_bin = _resolve_local_bin("input") if local else ""
        self.serial = serial or ("local" if local else None)
        self.screencap_timeout = screencap_timeout
        self._use_raw_screencap = not local  # 本地模式只用 PNG
        self._display: DisplayInfo | None = None
        # 最近一次截图的实际像素尺寸（物理像素，raw screencap 返回真实显示分辨率）
        self._frame_w: int | None = None
        self._frame_h: int | None = None

    # ------------------------------------------------------------------ 基础

    def _base_cmd(self) -> list[str]:
        if self.local:
            return []
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def run(self, *args: str, timeout: float = 15.0, binary: bool = False):
        """执行命令。binary=True 时返回原始 bytes。

        local 模式下 args 即为本地要执行的命令（如 "screencap", "-p"）。
        """
        if self.local:
            try:
                proc = subprocess.run(list(args), capture_output=True, timeout=timeout, check=False)
            except subprocess.TimeoutExpired as exc:
                raise AdbError(f"命令超时: {' '.join(args)}") from exc
            except FileNotFoundError as exc:
                raise AdbError(f"未找到本地命令: {' '.join(args)}（请确认已在 root shell 中运行）") from exc
            if proc.returncode != 0:
                err = proc.stderr.decode("utf-8", "ignore").strip()
                raise AdbError(f"命令失败 ({proc.returncode}): {' '.join(args)}\n{err}")
            return proc.stdout if binary else proc.stdout.decode("utf-8", "ignore")

        cmd = self._base_cmd() + list(args)
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb 命令超时: {' '.join(args)}") from exc
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "ignore").strip()
            raise AdbError(f"adb 命令失败 ({proc.returncode}): {' '.join(args)}\n{err}")
        return proc.stdout if binary else proc.stdout.decode("utf-8", "ignore")

    def shell(self, command: str, timeout: float = 15.0) -> str:
        if self.local:
            # 本地直接走 shell 解释命令（等价于 adb shell）
            try:
                proc = subprocess.run(
                    ["sh", "-c", command], capture_output=True, timeout=timeout, check=False
                )
            except FileNotFoundError as exc:
                raise AdbError(f"未找到 sh: {exc}") from exc
            return proc.stdout.decode("utf-8", "ignore").strip()
        return self.run("shell", command, timeout=timeout).strip()

    # ------------------------------------------------------------------ 连接

    @classmethod
    def list_devices(cls, adb_path: str = "adb", local: bool = False) -> list[tuple[str, str]]:
        """返回 [(serial, state), ...]。"""
        if local:
            # 本地模式：自检环境是否具备 root shell 能力
            if shutil.which("screencap") or os.path.isfile("/system/bin/screencap"):
                return [("local", "device")]
            return []
        exe = _resolve_adb(adb_path)
        try:
            out = subprocess.run([exe, "devices"], capture_output=True, timeout=15, check=False)
        except FileNotFoundError as exc:
            raise AdbError(f"未找到 adb 可执行文件: {adb_path}，请安装 Android Platform Tools") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError("adb devices 超时") from exc
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
        """连接无线设备，address 形如 192.168.1.10:5555。返回规范化后的 serial。"""
        exe = shutil.which(adb_path) or adb_path
        if ":" not in address:
            address = f"{address}:5555"
        proc = subprocess.run([exe, "connect", address], capture_output=True, timeout=timeout, check=False)
        msg = proc.stdout.decode("utf-8", "ignore").strip()
        if "connected" not in msg.lower() or "cannot" in msg.lower() or "failed" in msg.lower():
            raise AdbError(f"无线连接失败: {msg}")
        log.info("无线连接成功: %s", msg)
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
        raise AdbError("等待设备就绪超时，请检查 USB 调试授权或无线连接状态")

    # ------------------------------------------------------------------ 屏幕

    def get_display(self, refresh: bool = False) -> DisplayInfo:
        if self._display is not None and not refresh:
            return self._display

        size_out = self.shell("wm size")
        # 优先使用 Override size（部分设备被应用改过分辨率）
        m = re.search(r"Override size:\s*(\d+)x(\d+)", size_out) or re.search(
            r"Physical size:\s*(\d+)x(\d+)", size_out
        )
        if not m:
            raise AdbError(f"无法解析屏幕尺寸: {size_out}")
        w, h = int(m.group(1)), int(m.group(2))

        rot_out = self.shell("dumpsys input | grep -m 1 SurfaceOrientation") or ""
        rm = re.search(r"SurfaceOrientation:\s*(\d)", rot_out)
        if not rm:
            rot_out = self.shell("dumpsys display | grep -m 1 -o 'orientation=[0-9]'") or ""
            rm = re.search(r"orientation=(\d)", rot_out)
        rotation = int(rm.group(1)) if rm else 0

        # wm size 给的是竖屏基准尺寸，横屏时交换
        if rotation in (1, 3) and h > w:
            w, h = h, w

        self._display = DisplayInfo(width=w, height=h, rotation=rotation)
        log.debug("屏幕信息: %s", self._display)
        return self._display

    def screencap(self) -> np.ndarray:
        """截取当前屏幕，返回 BGR ndarray。

        同时缓存截图物理尺寸，供 tap/swipe 做 DPI/缩放自适应坐标换算。
        """
        if self.local:
            # 本地模式：screencap -p 直接输出 PNG
            data = self.run(self._screencap_bin, "-p", timeout=self.screencap_timeout, binary=True)
            img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise AdbError("本地截图解码失败（确认 screencap 可用且已授权）")
            self._frame_w, self._frame_h = img.shape[1], img.shape[0]
            return img

        if self._use_raw_screencap:
            try:
                img = self._screencap_raw()
                self._frame_w, self._frame_h = img.shape[1], img.shape[0]
                return img
            except AdbError as exc:
                log.warning("raw screencap 失败，降级为 PNG 模式: %s", exc)
                self._use_raw_screencap = False
        img = self._screencap_png()
        self._frame_w, self._frame_h = img.shape[1], img.shape[0]
        return img

    def _to_input_coords(self, x: float, y: float) -> tuple[float, float]:
        """把「截图物理像素坐标」换算为 ``input tap/swipe`` 期望的逻辑坐标。

        背景：``screencap`` 产出的是真实显示分辨率（物理像素），而 Android 的
        ``input tap`` 使用 ``wm size`` 报告的逻辑分辨率。当设备被改过 DPI、
        ``wm density``、``wm size`` Override（很多人为了游戏缩放会这么做）时，
        两者之间存在比例差 ``ratio = 物理宽 / 逻辑宽``，直接拿截图坐标去 tap 会
        系统性偏移。这里依据缓存的帧尺寸与显示尺寸自动补偿。
        """
        if self._frame_w and self._display and self._display.width:
            ratio = self._frame_w / self._display.width
            if abs(ratio - 1.0) > 1e-3:
                return x / ratio, y / ratio
        return x, y

    def _screencap_raw(self) -> np.ndarray:
        """screencap 不带参数时输出原始像素，头部为 w/h/format(/colorspace)。"""
        data = self.run("exec-out", "screencap", timeout=self.screencap_timeout, binary=True)
        if len(data) < 16:
            raise AdbError("screencap 返回数据过短")

        w, h, fmt = np.frombuffer(data[:12], dtype="<u4")
        # Android 9+ 头部多了 4 字节 colorspace
        for header in (16, 12):
            expected = int(w) * int(h) * 4
            if len(data) - header == expected:
                buf = np.frombuffer(data[header : header + expected], dtype=np.uint8)
                img = buf.reshape(int(h), int(w), 4)
                if int(fmt) == 1:  # RGBA_8888
                    return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        raise AdbError(f"screencap 尺寸不匹配: w={w} h={h} len={len(data)}")

    def _screencap_png(self) -> np.ndarray:
        data = self.run("exec-out", "screencap", "-p", timeout=self.screencap_timeout, binary=True)
        if b"\r\n" in data[:64] and not data.startswith(b"\x89PNG"):
            data = data.replace(b"\r\n", b"\n")
        img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise AdbError("PNG 截图解码失败")
        return img

    # ------------------------------------------------------------------ 输入

    def tap(self, x: int, y: int) -> None:
        # 截图物理坐标 → input 逻辑坐标（DPI/缩放自适应）
        ix, iy = self._to_input_coords(x, y)
        if self.local:
            self.run(self._input_bin, "tap", str(int(round(ix))), str(int(round(iy))))
        else:
            self.shell(f"input tap {int(round(ix))} {int(round(iy))}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        # 截图物理坐标 → input 逻辑坐标（DPI/缩放自适应）
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

    # ------------------------------------------------------------------ 应用

    def current_focus(self) -> str:
        out = self.shell("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        if not out:
            out = self.shell("dumpsys activity activities | grep -m 1 ResumedActivity")
        return out

    def is_package_running(self, package: str) -> bool:
        return bool(self.shell(f"pidof {package}"))

    def start_app(self, package: str) -> None:
        self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
