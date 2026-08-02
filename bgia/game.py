"""Game window detection: locate the Genshin / Cloud-Genshin process and compute the 16:9 render region (stripping notch safe-zones and letterbox bars)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

from .adb import AdbDevice

log = logging.getLogger(__name__)

# Package names per release channel
GENSHIN_PACKAGES: dict[str, str] = {
    "official": "com.miHoYo.Yuanshen",       # CN official
    "bilibili": "com.miHoYo.ys.bilibili",    # Bilibili (CN)
    "global": "com.miHoYo.GenshinImpact",    # Global (incl. Asia/EU/NA/TW-HK-MO)
    "cloud_cn": "com.miHoYo.cloudgames.ys",  # Cloud Genshin (CN)
    "cloud_global": "com.miHoYo.cloudgames.genshinimpact",  # Cloud Genshin (Global)
}

CLOUD_PACKAGES = {"com.miHoYo.cloudgames.ys", "com.miHoYo.cloudgames.genshinimpact"}

BASE_W, BASE_H = 1920, 1080
ASPECT = BASE_W / BASE_H


@dataclass
class GameWindow:
    """Position and scale relationship of the game's render region within the physical screen."""

    x: int
    y: int
    width: int
    height: int
    package: str
    is_cloud: bool

    @property
    def scale(self) -> float:
        """Scale factor relative to the 1920x1080 baseline."""
        return self.width / BASE_W

    def crop(self, frame: np.ndarray) -> np.ndarray:
        return frame[self.y : self.y + self.height, self.x : self.x + self.width]

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        """Convert a coordinate inside the render region into a physical screen coordinate (for tapping)."""
        return int(self.x + x), int(self.y + y)

    def from_base(self, x: float, y: float) -> tuple[int, int]:
        """Convert a 1920x1080-baseline coordinate into a physical screen coordinate."""
        s = self.scale
        return self.to_screen(x * s, y * s)


def detect_package(device: AdbDevice) -> str | None:
    """Return the package name of the foreground Genshin-related app."""
    focus = device.current_focus()
    for pkg in GENSHIN_PACKAGES.values():
        if pkg in focus:
            return pkg
    # If the foreground window is unavailable, fall back to checking whether the process is alive
    for pkg in GENSHIN_PACKAGES.values():
        if device.is_package_running(pkg):
            log.warning("package %s is running but not in the foreground; make sure the game is brought to the foreground", pkg)
            return pkg
    return None


def _trim_letterbox(frame: np.ndarray, threshold: int = 18) -> tuple[int, int, int, int]:
    """Strip pure-black borders on all sides and return (x, y, w, h). Used for Cloud-Genshin / letterboxed streaming frames."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = gray > threshold
    if not mask.any():
        return 0, 0, frame.shape[1], frame.shape[0]
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    x0, x1 = int(cols[0]), int(cols[-1]) + 1
    return x0, y0, x1 - x0, y1 - y0


def resolve_window(
    device: AdbDevice,
    frame: np.ndarray,
    package: str | None = None,
    trim_black: bool = True,
) -> GameWindow:
    """Compute the game's 16:9 render region.

Full-screen phones are usually wider than 16:9 (e.g. 20:9); Genshin leaves safe zones on both sides,
keeping the actual picture centered at 16:9. Cloud-Genshin streaming may have letterbox bars on the
top/bottom or left/right.
    """
    pkg = package or detect_package(device) or "unknown"
    is_cloud = pkg in CLOUD_PACKAGES

    fh, fw = frame.shape[:2]
    ox, oy, w, h = 0, 0, fw, fh

    if trim_black:
        bx, by, bw, bh = _trim_letterbox(frame)
        # Only adopt the trimmed box when it keeps at least half the frame; a fully black screen would
        # otherwise collapse the region to a tiny area and break downstream coordinate math.
        if bw >= fw * 0.5 and bh >= fh * 0.5:
            ox, oy, w, h = bx, by, bw, bh

    # Fit the region to a 16:9 box: keep the center and drop the excess width (sides) or height (top/bottom)
    if w / h > ASPECT:
        new_w = int(round(h * ASPECT))
        ox += (w - new_w) // 2
        w = new_w
    else:
        new_h = int(round(w / ASPECT))
        oy += (h - new_h) // 2
        h = new_h

    win = GameWindow(x=ox, y=oy, width=w, height=h, package=pkg, is_cloud=is_cloud)
    log.info(
        "game window detected: pkg=%s cloud=%s region=(%d,%d,%d,%d) scale=%.4f",
        pkg, is_cloud, ox, oy, w, h, win.scale,
    )
    return win
