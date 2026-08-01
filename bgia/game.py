"""游戏窗口识别：定位原神/云原神进程，并计算 16:9 渲染区域（去除刘海安全区/黑边）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

from .adb import AdbDevice

log = logging.getLogger(__name__)

# 各版本包名
GENSHIN_PACKAGES: dict[str, str] = {
    "official": "com.miHoYo.Yuanshen",       # 官服
    "bilibili": "com.miHoYo.ys.bilibili",    # B 服
    "global": "com.miHoYo.GenshinImpact",    # 国际服（含亚服/欧服/美服/港澳台）
    "cloud_cn": "com.miHoYo.cloudgames.ys",  # 云原神（国服）
    "cloud_global": "com.miHoYo.cloudgames.genshinimpact",  # 云·原神（国际）
}

CLOUD_PACKAGES = {"com.miHoYo.cloudgames.ys", "com.miHoYo.cloudgames.genshinimpact"}

BASE_W, BASE_H = 1920, 1080
ASPECT = BASE_W / BASE_H


@dataclass
class GameWindow:
    """游戏渲染区域在物理屏幕中的位置与缩放关系。"""

    x: int
    y: int
    width: int
    height: int
    package: str
    is_cloud: bool

    @property
    def scale(self) -> float:
        """相对 1920x1080 基准的缩放系数。"""
        return self.width / BASE_W

    def crop(self, frame: np.ndarray) -> np.ndarray:
        return frame[self.y : self.y + self.height, self.x : self.x + self.width]

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        """把渲染区内坐标换算为物理屏幕坐标（用于点击）。"""
        return int(self.x + x), int(self.y + y)

    def from_base(self, x: float, y: float) -> tuple[int, int]:
        """把 1920x1080 基准坐标换算为物理屏幕坐标。"""
        s = self.scale
        return self.to_screen(x * s, y * s)


def detect_package(device: AdbDevice) -> str | None:
    """返回当前前台的原神相关包名。"""
    focus = device.current_focus()
    for pkg in GENSHIN_PACKAGES.values():
        if pkg in focus:
            return pkg
    # 前台窗口拿不到时，退而检查进程是否存活
    for pkg in GENSHIN_PACKAGES.values():
        if device.is_package_running(pkg):
            log.warning("包 %s 在运行但不在前台，请确认游戏已切到前台", pkg)
            return pkg
    return None


def _trim_letterbox(frame: np.ndarray, threshold: int = 18) -> tuple[int, int, int, int]:
    """去掉四周纯黑边，返回 (x, y, w, h)。用于云原神/带黑边的串流画面。"""
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
    """计算游戏 16:9 渲染区域。

    手机全面屏通常比 16:9 更宽（如 20:9），原神会在两侧留出安全区，
    实际画面居中且保持 16:9；云原神串流则可能上下或左右带黑边。
    """
    pkg = package or detect_package(device) or "unknown"
    is_cloud = pkg in CLOUD_PACKAGES

    fh, fw = frame.shape[:2]
    ox, oy, w, h = 0, 0, fw, fh

    if trim_black:
        bx, by, bw, bh = _trim_letterbox(frame)
        # 只在黑边占比合理时采纳，避免整屏黑屏时误裁
        if bw >= fw * 0.5 and bh >= fh * 0.5:
            ox, oy, w, h = bx, by, bw, bh

    # 把区域收敛到 16:9，多余部分左右/上下居中裁掉
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
        "识别到游戏窗口: pkg=%s cloud=%s 区域=(%d,%d,%d,%d) 缩放=%.4f",
        pkg, is_cloud, ox, oy, w, h, win.scale,
    )
    return win
