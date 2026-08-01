#!/usr/bin/env python3
"""自动模板采集：基于当前手机截图，自动定位并裁剪三个必需模板。

无需手动量坐标。原理：
  - stop_auto.png  : 左上角「自动播放/停止自动播放」按钮（蓝青色胶囊 + OCR 命中“播/放/自/动”）
  - icon_option.png: 右侧对话选项气泡最左侧装饰（气泡区里最亮的竖条/小三角）
  - icon_exclamation.png: 选项前的黄色感叹号（HSV 黄色检测）

用法:
    .venv/bin/python tools/auto_grab.py            # 自动采集全部三张
    .venv/bin/python tools/auto_grab.py --name stop_auto.png   # 只采指定
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bgia.adb import AdbDevice  # noqa: E402
from bgia.game import resolve_window  # noqa: E402
from bgia.vision import ASSETS_DIR, OcrEngine  # noqa: E402

BASE_W = 1920


def capture(serial: str | None):
    dev = AdbDevice(serial=serial)
    dev.wait_ready()
    frame = dev.screencap()
    win = resolve_window(dev, frame)
    return win.crop(frame), win


def save(crop: np.ndarray, name: str, scale: float) -> Path:
    if abs(scale - 1.0) > 1e-3:
        inv = 1.0 / scale
        nw = max(1, int(round(crop.shape[1] * inv)))
        nh = max(1, int(round(crop.shape[0] * inv)))
        interp = cv2.INTER_AREA if inv < 1 else cv2.INTER_CUBIC
        crop = cv2.resize(crop, (nw, nh), interpolation=interp)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    out = ASSETS_DIR / name
    cv2.imwrite(str(out), crop)
    print(f"  [保存] {name}  {crop.shape[1]}x{crop.shape[0]}  -> {out}")
    return out


# ---------------------------------------------------------------- 定位器

def grab_stop_auto(frame: np.ndarray, scale: float, ocr: OcrEngine) -> np.ndarray | None:
    """左上角自动播放按钮：蓝青色胶囊 + OCR 命中播放相关字。"""
    h, w = frame.shape[:2]
    roi = frame[0 : h // 8, 0 : w // 5]
    rh, rw = roi.shape[:2]

    # 1) 颜色：原神自动播放按钮是半透明深蓝青胶囊
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # 蓝青色范围（含暂停图标白色）
    blue = cv2.inRange(hsv, (85, 40, 60), (130, 255, 255))
    white = cv2.inRange(hsv, (0, 0, 200), (180, 40, 255))
    mask = cv2.bitwise_or(blue, white)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cand = [c for c in cnts if cv2.contourArea(c) > 200]
    if not cand:
        # 2) 退回 OCR：左上角文字区域
        crop = roi[int(10 * scale): int(70 * scale), int(10 * scale): int(360 * scale)]
        for r in ocr.recognize(crop):
            if any(ch in r.text for ch in ("播", "放", "自", "动", "暂")):
                x, y, cw, ch = r.x, r.y, r.width, r.height
                sx, sy = int(10 * scale), int(10 * scale)
                return roi[sy + max(0, y - 6): sy + y + ch + 6, sx + max(0, x - 6): sx + x + cw + 6]
        print("  [跳过] 未定位到自动播放按钮（颜色/OCR 均未命中）")
        return None

    x, y, cw, ch = cv2.boundingRect(np.vstack(cand))
    # 适当外扩，保留完整胶囊
    pad = int(8 * scale)
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(rw, x + cw + pad), min(rh, y + ch + pad)
    return roi[y0:y1, x0:x1]


def grab_option_icon(frame: np.ndarray, scale: float) -> np.ndarray | None:
    """选项按钮左侧的小三角/箭头图标：在选项 ROI 内找白色小亮块（约 33x33）。

    原神选项按钮是半透明深底 + 左侧白色小三角，整体不是亮块，但小三角是亮块。
    取最靠上的一个作为模板（最上方选项最稳定）。
    """
    h, w = frame.shape[:2]
    x0, y0 = w // 2, h // 12
    x1, y1 = w - w // 6, h - h // 12
    roi = frame[y0:y1, x0:x1]
    rh, rw = roi.shape[:2]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # 小三角图标是白色，在暗背景上显亮
    _, bin_ = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(bin_, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # 过滤：近似方形小亮块（选项图标约 30~45px）
    cands = []
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        if 18 * scale <= cw <= 60 * scale and 18 * scale <= ch <= 60 * scale and cv2.contourArea(c) > 300:
            cands.append((x, y, cw, ch))
    if not cands:
        print("  [跳过] 未检测到选项图标（请确认手机停在选项界面）")
        return None

    # 取最靠上的图标作为模板
    cands.sort(key=lambda b: b[1])
    bx, by, bw, bh = cands[0]
    pad = int(6 * scale)
    ix0 = max(0, bx - pad)
    ix1 = min(rw, bx + bw + pad)
    iy0 = max(0, by - pad)
    iy1 = min(rh, by + bh + pad)
    return roi[iy0:iy1, ix0:ix1]


def grab_exclamation(frame: np.ndarray, scale: float) -> np.ndarray | None:
    """选项前的黄色感叹号：HSV 黄色检测 + 竖直条形状。"""
    h, w = frame.shape[:2]
    x0, y0 = w // 2, h // 12
    x1, y1 = w - w // 6, h - h // 12
    roi = frame[y0:y1, x0:x1]
    rh, rw = roi.shape[:2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # 黄色/橙黄感叹号
    yellow = cv2.inRange(hsv, (18, 120, 150), (34, 255, 255))
    cnts, _ = cv2.findContours(yellow, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # 感叹号是细高形状：高/宽 > 2
    cands = []
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw > 3 and ch > 12 * scale and ch / max(cw, 1) > 2.0:
            cands.append((x, y, cw, ch))
    if not cands:
        print("  [跳过] 未检测到黄色感叹号（当前选项可能无任务标记）")
        return None
    cands.sort(key=lambda b: b[1])
    x, y, cw, ch = cands[0]
    pad = int(6 * scale)
    return roi[max(0, y - pad): min(rh, y + ch + pad), max(0, x - pad): min(rw, x + cw + pad)]


GRABBER = {
    "stop_auto.png": grab_stop_auto,
    "icon_option.png": grab_option_icon,
    "icon_exclamation.png": grab_exclamation,
}


def main() -> int:
    p = argparse.ArgumentParser(description="自动模板采集")
    p.add_argument("--name", help="只采集指定模板，如 stop_auto.png")
    p.add_argument("-s", "--serial")
    p.add_argument("--from-shot", help="从指定截图文件离线采集（不连设备）", default=None)
    args = p.parse_args()

    if args.from_shot:
        from bgia.vision import _load_template  # noqa: F401

        img = cv2.imread(args.from_shot)
        if img is None:
            print(f"[错误] 无法读取截图: {args.from_shot}")
            return 1
        # 用相同的渲染区裁剪逻辑（假设截图已经是渲染区，即 16:9）
        h, w = img.shape[:2]
        scale = w / BASE_W
        frame = img
        win = type("W", (), {"scale": scale, "width": w, "height": h})()
        print(f"==> 离线模式: {args.from_shot}  {w}x{h} 缩放={scale:.4f}")
    else:
        print("==> 抓取当前画面...")
        frame, win = capture(args.serial)
        print(f"    渲染区 {win.width}x{win.height} 缩放={win.scale:.4f}")

    ocr = OcrEngine()
    names = [args.name] if args.name else list(GRABBER.keys())

    for name in names:
        if name not in GRABBER:
            print(f"  [未知模板] {name}")
            continue
        print(f"==> 采集 {name}")
        gb = GRABBER[name]
        if name == "stop_auto.png":
            crop = gb(frame, win.scale, ocr)
        else:
            crop = gb(frame, win.scale)
        if crop is not None and crop.size > 0:
            save(crop, name, win.scale)
        else:
            print(f"  [失败] {name} 未采到，请确认手机当前停在对应界面后重试")

    print("\n完成。缺失的模板可再次运行本脚本补齐。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
