#!/usr/bin/env python3
"""Automatic template capture: locate and crop the three required templates from the current phone screenshot.

No manual coordinate measurement needed. Principle:
  - stop_auto.png  : the top-left "Auto-Play / Stop Auto-Play" button (cyan capsule + OCR hit on 播/放/自/动)
  - icon_option.png: the leftmost decoration of the right-side dialogue-option bubble (brightest vertical bar / small triangle in the bubble area)
  - icon_exclamation.png: the yellow exclamation mark before an option (HSV yellow detection)

Usage:
    .venv/bin/python tools/auto_grab.py            # auto-capture all three
    .venv/bin/python tools/auto_grab.py --name stop_auto.png   # capture only the specified one
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
    print(f"  [saved] {name}  {crop.shape[1]}x{crop.shape[0]}  -> {out}")
    return out


# ---------------------------------------------------------------- Locators

def grab_stop_auto(frame: np.ndarray, scale: float, ocr: OcrEngine) -> np.ndarray | None:
    """Top-left auto-play button: cyan capsule + OCR hit on play-related characters."""
    h, w = frame.shape[:2]
    roi = frame[0 : h // 8, 0 : w // 5]
    rh, rw = roi.shape[:2]

    # 1) Color: Genshin's auto-play button is a semi-transparent dark cyan capsule
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # cyan range (includes the white of the pause icon)
    blue = cv2.inRange(hsv, (85, 40, 60), (130, 255, 255))
    white = cv2.inRange(hsv, (0, 0, 200), (180, 40, 255))
    mask = cv2.bitwise_or(blue, white)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cand = [c for c in cnts if cv2.contourArea(c) > 200]
    if not cand:
        # 2) Fall back to OCR on the top-left text region
        crop = roi[int(10 * scale): int(70 * scale), int(10 * scale): int(360 * scale)]
        for r in ocr.recognize(crop):
            if any(ch in r.text for ch in ("播", "放", "自", "动", "暂")):
                x, y, cw, ch = r.x, r.y, r.width, r.height
                sx, sy = int(10 * scale), int(10 * scale)
                return roi[sy + max(0, y - 6): sy + y + ch + 6, sx + max(0, x - 6): sx + x + cw + 6]
        print("  [skip] auto-play button not located (neither color nor OCR matched)")
        return None

    x, y, cw, ch = cv2.boundingRect(np.vstack(cand))
    # expand slightly to keep the full capsule
    pad = int(8 * scale)
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(rw, x + cw + pad), min(rh, y + ch + pad)
    return roi[y0:y1, x0:x1]


def grab_option_icon(frame: np.ndarray, scale: float) -> np.ndarray | None:
    """The small triangle/arrow icon on the left of an option button: locate the small white bright block (about 33x33) inside the option ROI.

Genshin's option button is a semi-transparent dark background plus a small white triangle on the left; the whole button is not bright, but the small triangle is. Take the topmost one as the template (the top option is the most stable).
    """
    h, w = frame.shape[:2]
    x0, y0 = w // 2, h // 12
    x1, y1 = w - w // 6, h - h // 12
    roi = frame[y0:y1, x0:x1]
    rh, rw = roi.shape[:2]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # the small triangle icon is white and stands out on the dark background
    _, bin_ = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(bin_, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # filter: roughly square small bright block (option icon ~30~45px)
    cands = []
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        if 18 * scale <= cw <= 60 * scale and 18 * scale <= ch <= 60 * scale and cv2.contourArea(c) > 300:
            cands.append((x, y, cw, ch))
    if not cands:
        print("  [skip] no option icon detected (make sure the phone is on the dialogue-option screen)")
        return None

    # take the topmost icon as the template
    cands.sort(key=lambda b: b[1])
    bx, by, bw, bh = cands[0]
    pad = int(6 * scale)
    ix0 = max(0, bx - pad)
    ix1 = min(rw, bx + bw + pad)
    iy0 = max(0, by - pad)
    iy1 = min(rh, by + bh + pad)
    return roi[iy0:iy1, ix0:ix1]


def grab_exclamation(frame: np.ndarray, scale: float) -> np.ndarray | None:
    """The yellow exclamation mark before an option: HSV yellow detection plus vertical-bar shape."""
    h, w = frame.shape[:2]
    x0, y0 = w // 2, h // 12
    x1, y1 = w - w // 6, h - h // 12
    roi = frame[y0:y1, x0:x1]
    rh, rw = roi.shape[:2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # yellow / orange-yellow exclamation
    yellow = cv2.inRange(hsv, (18, 120, 150), (34, 255, 255))
    cnts, _ = cv2.findContours(yellow, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # the exclamation mark is a thin, tall shape: height/width > 2
    cands = []
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw > 3 and ch > 12 * scale and ch / max(cw, 1) > 2.0:
            cands.append((x, y, cw, ch))
    if not cands:
        print("  [skip] no yellow exclamation detected (current option may have no quest marker)")
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
    p = argparse.ArgumentParser(description="Automatic template capture")
    p.add_argument("--name", help="capture only the specified template, e.g. stop_auto.png")
    p.add_argument("-s", "--serial")
    p.add_argument("--from-shot", help="capture offline from a screenshot file (no device connection)", default=None)
    args = p.parse_args()

    if args.from_shot:
        from bgia.vision import _load_template  # noqa: F401

        img = cv2.imread(args.from_shot)
        if img is None:
            print(f"[error] cannot read screenshot: {args.from_shot}")
            return 1
        # use the same render-region crop logic (assume the screenshot is already the render region, i.e. 16:9)
        h, w = img.shape[:2]
        scale = w / BASE_W
        frame = img
        win = type("W", (), {"scale": scale, "width": w, "height": h})()
        print(f"==> offline mode: {args.from_shot}  {w}x{h}  scale={scale:.4f}")
    else:
        print("==> grabbing the current screen...")
        frame, win = capture(args.serial)
        print(f"    render region {win.width}x{win.height}  scale={win.scale:.4f}")

    ocr = OcrEngine()
    names = [args.name] if args.name else list(GRABBER.keys())

    for name in names:
        if name not in GRABBER:
            print(f"  [unknown template] {name}")
            continue
        print(f"==> capturing {name}")
        gb = GRABBER[name]
        if name == "stop_auto.png":
            crop = gb(frame, win.scale, ocr)
        else:
            crop = gb(frame, win.scale)
        if crop is not None and crop.size > 0:
            save(crop, name, win.scale)
        else:
            print(f"  [failed] {name} not captured; make sure the phone is on the matching screen, then retry")

    print("\nDone. Re-run this script to fill in any missing templates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
