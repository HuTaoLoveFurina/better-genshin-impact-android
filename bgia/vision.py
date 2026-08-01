"""视觉识别层：模板匹配、OCR、橙色选项判定、黑屏检测。

坐标基准与 BetterGI 一致：所有模板与 ROI 均以 1920x1080 定义，运行时按缩放系数换算。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "1920x1080"


@dataclass
class Match:
    x: int
    y: int
    width: int
    height: int
    score: float = 0.0
    text: str = ""
    click: tuple[int, int] | None = None  # 可选：推荐的点击坐标（相对 frame）

    @property
    def center(self) -> tuple[int, int]:
        if self.click:
            return self.click
        return self.x + self.width // 2, self.y + self.height // 2

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def right(self) -> int:
        return self.x + self.width


# ---------------------------------------------------------------- 模板匹配


@lru_cache(maxsize=64)
def _load_template(name: str) -> np.ndarray | None:
    path = ASSETS_DIR / name
    if not path.exists():
        log.warning("模板缺失: %s", path)
        return None
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        log.warning("模板读取失败: %s", path)
    return img


@lru_cache(maxsize=128)
def _scaled_template(name: str, scale_key: int) -> np.ndarray | None:
    """按缩放系数缓存缩放后的模板。scale_key = round(scale * 1000)。"""
    tpl = _load_template(name)
    if tpl is None:
        return None
    scale = scale_key / 1000.0
    if abs(scale - 1.0) < 1e-3:
        return tpl
    h, w = tpl.shape[:2]
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    return cv2.resize(tpl, (nw, nh), interpolation=interp)


def match_template(
    frame: np.ndarray,
    name: str,
    scale: float,
    threshold: float = 0.8,
    roi: tuple[int, int, int, int] | None = None,
    mode: int = cv2.TM_CCOEFF_NORMED,
) -> Match | None:
    """在 frame 中查找模板，返回最佳匹配（坐标相对 frame 原点）。"""
    tpl = _scaled_template(name, int(round(scale * 1000)))
    if tpl is None:
        return None

    ox, oy = 0, 0
    target = frame
    if roi is not None:
        rx, ry, rw, rh = roi
        rx, ry = max(0, rx), max(0, ry)
        rw = min(rw, frame.shape[1] - rx)
        rh = min(rh, frame.shape[0] - ry)
        if rw <= 0 or rh <= 0:
            return None
        target = frame[ry : ry + rh, rx : rx + rw]
        ox, oy = rx, ry

    th, tw = tpl.shape[:2]
    if target.shape[0] < th or target.shape[1] < tw:
        return None

    res = cv2.matchTemplate(target, tpl, mode)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < threshold:
        return None
    return Match(x=ox + max_loc[0], y=oy + max_loc[1], width=tw, height=th, score=float(max_val))


def match_template_multi(
    frame: np.ndarray,
    name: str,
    scale: float,
    threshold: float = 0.8,
    roi: tuple[int, int, int, int] | None = None,
    max_count: int = 10,
) -> list[Match]:
    """多目标模板匹配 + NMS 去重。"""
    tpl = _scaled_template(name, int(round(scale * 1000)))
    if tpl is None:
        return []

    ox, oy = 0, 0
    target = frame
    if roi is not None:
        rx, ry, rw, rh = roi
        rx, ry = max(0, rx), max(0, ry)
        rw = min(rw, frame.shape[1] - rx)
        rh = min(rh, frame.shape[0] - ry)
        if rw <= 0 or rh <= 0:
            return []
        target = frame[ry : ry + rh, rx : rx + rw]
        ox, oy = rx, ry

    th, tw = tpl.shape[:2]
    if target.shape[0] < th or target.shape[1] < tw:
        return []

    res = cv2.matchTemplate(target, tpl, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(res >= threshold)
    cands = sorted(
        (Match(x=ox + int(x), y=oy + int(y), width=tw, height=th, score=float(res[y, x])) for y, x in zip(ys, xs)),
        key=lambda m: m.score,
        reverse=True,
    )

    kept: list[Match] = []
    for c in cands:
        if all(abs(c.x - k.x) >= tw * 0.5 or abs(c.y - k.y) >= th * 0.5 for k in kept):
            kept.append(c)
        if len(kept) >= max_count:
            break
    return kept


# ---------------------------------------------------------------- 颜色判定


def is_orange_option(img: np.ndarray, ratio_threshold: float = 0.06) -> bool:
    """BetterGI 逻辑：橙色文字占比超过阈值即视为关键剧情选项。"""
    if img.size == 0:
        return False
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([11, 120, 120]), np.array([34, 255, 255]))
    return float(np.count_nonzero(mask)) / mask.size > ratio_threshold


def black_ratio(frame: np.ndarray, low: int = 0, high: int = 40) -> float:
    """中间 1/3 区域的黑色像素占比，用于黑屏演出检测。"""
    h, w = frame.shape[:2]
    mid = frame[h // 3 : h * 2 // 3, :]
    gray = cv2.cvtColor(mid, cv2.COLOR_BGR2GRAY)
    mask = cv2.inRange(gray, low, high)
    return float(np.count_nonzero(mask)) / mask.size


def frame_diff_ratio(a: np.ndarray | None, b: np.ndarray | None, thresh: int = 12) -> float:
    """两帧差异比例，用于判断画面是否静止（等待中）。"""
    if a is None or b is None or a.shape != b.shape:
        return 1.0
    ga = cv2.cvtColor(cv2.resize(a, (192, 108)), cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(cv2.resize(b, (192, 108)), cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(ga, gb)
    return float(np.count_nonzero(diff > thresh)) / diff.size


# ---------------------------------------------------------------- OCR


class OcrEngine:
    """RapidOCR 封装，延迟初始化；不可用时降级为空结果。

    同时兼容两代包：
      - rapidocr >= 2.x        ：``from rapidocr import RapidOCR``，返回 RapidOCROutput 对象
      - rapidocr-onnxruntime   ：旧包（仅支持 Python < 3.13），返回 (结果列表, 耗时) 元组
    """

    def __init__(self) -> None:
        self._engine = None
        self._available: bool | None = None

    def _ensure(self) -> bool:
        if self._available is not None:
            return self._available

        last_err: Exception | None = None
        for module, label in (("rapidocr", "rapidocr"), ("rapidocr_onnxruntime", "rapidocr-onnxruntime")):
            try:
                mod = __import__(module, fromlist=["RapidOCR"])
                self._engine = mod.RapidOCR()
                self._available = True
                log.info("OCR 引擎已加载: %s", label)
                return True
            except Exception as exc:  # pragma: no cover - 依赖缺失路径
                last_err = exc

        log.error(
            "OCR 引擎加载失败，选项文本识别将降级为按位置点击: %s\n"
            "  安装方式: pip install rapidocr onnxruntime",
            last_err,
        )
        self._available = False
        return False

    @staticmethod
    def _normalize(raw) -> list[tuple]:
        """把两代 API 的返回值统一为 [(box, text, score), ...]。"""
        if raw is None:
            return []

        # rapidocr >= 2.x: RapidOCROutput(boxes=..., txts=..., scores=...)
        if hasattr(raw, "boxes"):
            boxes = getattr(raw, "boxes", None)
            if boxes is not None and len(boxes) > 0:
                txts = getattr(raw, "txts", None) or []
                scores = getattr(raw, "scores", None) or []
                return [
                    (boxes[i], txts[i] if i < len(txts) else "", scores[i] if i < len(scores) else 0.0)
                    for i in range(len(boxes))
                ]
            return []

        # 旧版: (结果列表, 耗时)
        if isinstance(raw, tuple) and len(raw) == 2 and isinstance(raw[0], (list, type(None))):
            raw = raw[0] or []
        return [item for item in raw if item and len(item) >= 3]

    def recognize(self, img: np.ndarray, upscale: int | None = None) -> list[Match]:
        """返回带文本与包围盒的结果，坐标相对传入图像。

        upscale: 放大倍数（针对小字号选项文本，提升识别率）。默认按图像高度自适应。
        """
        if img.size == 0 or not self._ensure():
            return []
        # 放大有助于小字号识别
        scale = float(upscale) if upscale else (2.0 if img.shape[0] < 60 else 1.0)
        src = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR) if scale != 1.0 else img
        try:
            raw = self._engine(src)
        except Exception as exc:  # pragma: no cover
            log.warning("OCR 识别异常: %s", exc)
            return []

        result = self._normalize(raw)
        if not result:
            return []

        out: list[Match] = []
        for box, text, score in result:
            pts = np.array(box, dtype=np.float32) / scale
            x0, y0 = pts[:, 0].min(), pts[:, 1].min()
            x1, y1 = pts[:, 0].max(), pts[:, 1].max()
            out.append(
                Match(
                    x=int(x0),
                    y=int(y0),
                    width=int(x1 - x0),
                    height=int(y1 - y0),
                    score=float(score),
                    text=str(text).strip(),
                )
            )
        return out
