#!/usr/bin/env python3
"""Template capture tool: crop templates from a real phone screenshot, auto-normalize to the 1920x1080 baseline, and save.

Usage:
    # 1. Grab the current screen first (saved to shot.png, also prints render-region info)
    python tools/grab_template.py shot

    # 2. Measure the target icon's pixel box in shot.png with any image viewer, then crop
    python tools/grab_template.py crop --rect 120,40,64,64 --name stop_auto.png

    # 3. Interactive box selection (needs a GUI environment, install opencv-python not headless)
    python tools/grab_template.py pick --name icon_option.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bgia.adb import AdbDevice  # noqa: E402
from bgia.game import resolve_window  # noqa: E402
from bgia.vision import ASSETS_DIR  # noqa: E402

BASE_W = 1920


def capture(serial: str | None):
    dev = AdbDevice(serial=serial)
    dev.wait_ready()
    frame = dev.screencap()
    win = resolve_window(dev, frame)
    return win.crop(frame), win


def save_template(crop, name: str, scale: float) -> Path:
    """Scale the on-device crop back to the 1920x1080 baseline, then save."""
    if abs(scale - 1.0) > 1e-3:
        inv = 1.0 / scale
        nw = max(1, int(round(crop.shape[1] * inv)))
        nh = max(1, int(round(crop.shape[0] * inv)))
        interp = cv2.INTER_AREA if inv < 1 else cv2.INTER_CUBIC
        crop = cv2.resize(crop, (nw, nh), interpolation=interp)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    out = ASSETS_DIR / name
    cv2.imwrite(str(out), crop)
    print(f"saved template: {out}  size={crop.shape[1]}x{crop.shape[0]}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="template capture tool")
    p.add_argument("action", choices=["shot", "crop", "pick"])
    p.add_argument("-s", "--serial")
    p.add_argument("--rect", help="crop region x,y,w,h (relative to render-region top-left)")
    p.add_argument("--name", help="template file name, e.g. icon_option.png")
    p.add_argument("--out", default="shot.png", help="output path for shot mode")
    args = p.parse_args()

    frame, win = capture(args.serial)
    print(f"render region: {win.width}x{win.height}  scale={win.scale:.4f}")

    if args.action == "shot":
        cv2.imwrite(args.out, frame)
        print(f"saved screenshot: {args.out}")
        print("hint: measure coordinates with this image's top-left corner as origin")
        return 0

    if not args.name:
        p.error("crop/pick mode requires --name")

    if args.action == "crop":
        if not args.rect:
            p.error("crop mode requires --rect x,y,w,h")
        x, y, w, h = (int(v) for v in args.rect.split(","))
        crop = frame[y : y + h, x : x + w]
        if crop.size == 0:
            print("invalid crop region")
            return 1
        save_template(crop, args.name, win.scale)
        return 0

    # pick: interactive box selection
    roi = cv2.selectROI("drag to select the target, Enter to confirm / c to cancel", frame, showCrosshair=True)
    cv2.destroyAllWindows()
    x, y, w, h = (int(v) for v in roi)
    if w == 0 or h == 0:
        print("canceled")
        return 1
    print(f"selected region: {x},{y},{w},{h}")
    save_template(frame[y : y + h, x : x + w], args.name, win.scale)
    return 0


if __name__ == "__main__":
    sys.exit(main())
