"""Preload / download the RapidOCR recognition model for the given game language.

Usage:
    python tools/ensure_ocr.py <game_lang>

<game_lang> is the Genshin client language code, e.g. zh-CN / en / ja / ko / ru / fr ...
Missing models are downloaded automatically when RapidOCR is constructed (requires network access).
Exit code 0 means success; non-zero means failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script directly: add the project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bgia.i18n import get_ocr_lang  # noqa: E402
from bgia.vision import OcrEngine  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python tools/ensure_ocr.py <game_lang>", file=sys.stderr)
        return 2
    game_lang = sys.argv[1]
    ocr_lang = get_ocr_lang(game_lang)
    print(f"[ensure_ocr] game language={game_lang} -> OCR model={ocr_lang}, preloading/downloading...")
    try:
        engine = OcrEngine(lang=ocr_lang)
        ok = engine._ensure()
    except Exception as exc:  # pragma: no cover - runtime dependency issue
        print(f"[ensure_ocr] failed: {exc}", file=sys.stderr)
        return 1
    if not ok:
        print("[ensure_ocr] OCR engine unavailable (missing dependency); option-text recognition will degrade.", file=sys.stderr)
        return 1
    print(f"[ensure_ocr] done, OCR model={ocr_lang} ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
