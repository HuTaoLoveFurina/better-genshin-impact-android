#!/usr/bin/env python3
"""模板采集工具：从手机实机截图裁剪模板，自动归一化到 1920x1080 基准并保存。

用法：
    # 1. 先抓一张当前画面（保存到 shot.png，同时输出渲染区信息）
    python tools/grab_template.py shot

    # 2. 用任意看图软件量出目标图标在 shot.png 中的像素框，然后裁剪
    python tools/grab_template.py crop --rect 120,40,64,64 --name stop_auto.png

    # 3. 交互式框选（需要有 GUI 环境，安装 opencv-python 而非 headless）
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
    """把实机裁剪结果缩放回 1920x1080 基准再保存。"""
    if abs(scale - 1.0) > 1e-3:
        inv = 1.0 / scale
        nw = max(1, int(round(crop.shape[1] * inv)))
        nh = max(1, int(round(crop.shape[0] * inv)))
        interp = cv2.INTER_AREA if inv < 1 else cv2.INTER_CUBIC
        crop = cv2.resize(crop, (nw, nh), interpolation=interp)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    out = ASSETS_DIR / name
    cv2.imwrite(str(out), crop)
    print(f"已保存模板: {out}  尺寸={crop.shape[1]}x{crop.shape[0]}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="模板采集工具")
    p.add_argument("action", choices=["shot", "crop", "pick"])
    p.add_argument("-s", "--serial")
    p.add_argument("--rect", help="裁剪区域 x,y,w,h（相对渲染区左上角）")
    p.add_argument("--name", help="模板文件名，如 icon_option.png")
    p.add_argument("--out", default="shot.png", help="shot 模式输出路径")
    args = p.parse_args()

    frame, win = capture(args.serial)
    print(f"渲染区: {win.width}x{win.height}  缩放={win.scale:.4f}")

    if args.action == "shot":
        cv2.imwrite(args.out, frame)
        print(f"已保存截图: {args.out}")
        print("提示: 量取的坐标请以此图左上角为原点")
        return 0

    if not args.name:
        p.error("crop/pick 模式需要 --name")

    if args.action == "crop":
        if not args.rect:
            p.error("crop 模式需要 --rect x,y,w,h")
        x, y, w, h = (int(v) for v in args.rect.split(","))
        crop = frame[y : y + h, x : x + w]
        if crop.size == 0:
            print("裁剪区域无效")
            return 1
        save_template(crop, args.name, win.scale)
        return 0

    # pick: 交互式框选
    roi = cv2.selectROI("拖动框选目标，回车确认 / c 取消", frame, showCrosshair=True)
    cv2.destroyAllWindows()
    x, y, w, h = (int(v) for v in roi)
    if w == 0 or h == 0:
        print("已取消")
        return 1
    print(f"选中区域: {x},{y},{w},{h}")
    save_template(frame[y : y + h, x : x + w], args.name, win.scale)
    return 0


if __name__ == "__main__":
    sys.exit(main())
