#!/usr/bin/env python3
"""Single-frame recognition verifier: runs the full decision chain on a screenshot without actually tapping, and prints the conclusion of each step.

Usage:
    .venv/bin/python tools/verify_frame.py shot.png
    .venv/bin/python tools/verify_frame.py            # defaults to shot.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bgia.config import Config  # noqa: E402
from bgia.game import resolve_window, GameWindow  # noqa: E402
from bgia.autoskip import AutoSkipTask  # noqa: E402
from bgia.vision import Match  # noqa: E402


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "shot.png"
    if not path.exists():
        print(f"[ERROR] screenshot not found: {path}")
        return 1

    frame_full = cv2.imread(str(path))
    cfg = Config._apply_env(Config())
    task = AutoSkipTask.__new__(AutoSkipTask)
    task.config = cfg
    task.ocr = __import__("bgia.vision", fromlist=["OcrEngine"]).OcrEngine()
    class _FakeDev:
        def current_focus(self):
            return cfg.package or ""

        def is_package_running(self, p):
            return True

    task.window = resolve_window(_FakeDev(), frame_full, cfg.package)
    task._paused_reason = None

    print(f"==> input: {path}  {frame_full.shape[1]}x{frame_full.shape[0]}")
    print(f"==> render region: x={task.window.x} y={task.window.y} "
          f"{task.window.width}x{task.window.height} scale={task.window.scale:.4f}\n")

    frame = task.window.crop(frame_full)
    print("[1] playing-state check (_is_playing):")
    playing = task._is_playing(frame)
    print(f"    -> {playing}")
    if playing:
        m = task._find(frame, "stop_auto.png")
        print(f"    stop_auto hit: {None if not m else (m.x, m.y, round(m.score,3))}")

    print("\n[2] option check (_handle_options, detection only, no tapping):")
    roi = task._option_roi(frame)
    print(f"    option ROI: {roi}")
    excl = task._find(frame, "icon_exclamation.png", roi=roi)
    print(f"    exclamation (quest-critical): {None if not excl else (excl.x, excl.y, round(excl.score,3))}")
    bubbles = task._find_multi(frame, "icon_option.png", roi) if hasattr(task, "_find_multi") else None
    # call vision directly
    from bgia.vision import match_template_multi
    bubbles = match_template_multi(frame, "icon_option.png", task._scale(), cfg.template_threshold, roi)
    print(f"    option-bubble count (threshold {cfg.template_threshold}): {len(bubbles)}")
    for i, b in enumerate(bubbles[:8]):
        print(f"      #{i} ({b.x},{b.y},{b.width}x{b.height}) score={b.score:.3f}")
    if bubbles:
        texts = task._read_options(frame, roi)
        print(f"    OCR text ({len(texts)}):")
        for i, t in enumerate(texts):
            print(f"      [{i}] {t.text!r} orange={t.score>0}")
        if texts:
            choice = task._decide_option(texts)
            print(f"    decision: {None if choice is None else (choice[0], choice[1].text)}")

    print("\n[3] black-screen check:")
    from bgia.vision import black_ratio
    r = black_ratio(frame)
    print(f"    black ratio={r:.3f}  range [{cfg.black_ratio_min},{cfg.black_ratio_max}] -> "
          f"{cfg.black_ratio_min <= r <= cfg.black_ratio_max}")

    print("\n[4] pop-up page check:")
    close = task._find(frame, "page_close.png")
    print(f"    page_close: {None if not close else (close.x, close.y)}")
    hangout = task._find(frame, "hangout_skip.png")
    print(f"    hangout_skip: {None if not hangout else (hangout.x, hangout.y)}")

    print("\nDone. This was recognition-only verification; no taps were performed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
