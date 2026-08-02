"""预热 / 下载指定游戏语言对应的 RapidOCR 识别模型。

用法:
    python tools/ensure_ocr.py <game_lang>

<game_lang> 为原神客户端语言代码，例如 zh-CN / en / ja / ko / ru / fr ...
缺失的模型会在构造 RapidOCR 时自动下载（需联网）。
退出码 0 表示成功，非 0 表示失败。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 允许以脚本方式直接运行：把项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bgia.i18n import get_ocr_lang  # noqa: E402
from bgia.vision import OcrEngine  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tools/ensure_ocr.py <game_lang>", file=sys.stderr)
        return 2
    game_lang = sys.argv[1]
    ocr_lang = get_ocr_lang(game_lang)
    print(f"[ensure_ocr] 游戏语言={game_lang} -> OCR 模型={ocr_lang}，正在预热/下载...")
    try:
        engine = OcrEngine(lang=ocr_lang)
        ok = engine._ensure()
    except Exception as exc:  # pragma: no cover - 运行期依赖问题
        print(f"[ensure_ocr] 失败: {exc}", file=sys.stderr)
        return 1
    if not ok:
        print("[ensure_ocr] OCR 引擎不可用（依赖缺失），选项文本识别将降级。", file=sys.stderr)
        return 1
    print(f"[ensure_ocr] 完成，OCR 模型={ocr_lang} 就绪。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
