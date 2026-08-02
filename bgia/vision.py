"""Vision recognition layer: template matching, OCR, orange-option detection, and black-screen detection.

All templates and ROIs are defined against a 1920x1080 baseline and scaled at runtime by the render-region ratio, mirroring the coordinate convention used by BetterGI.
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
    click: tuple[int, int] | None = None  # optional: recommended tap coordinate (relative to the frame)

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


# ---------------------------------------------------------------- Template matching


@lru_cache(maxsize=64)
def _load_template(name: str) -> np.ndarray | None:
    path = ASSETS_DIR / name
    if not path.exists():
        log.warning("template missing: %s", path)
        return None
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        log.warning("failed to read template: %s", path)
    return img


@lru_cache(maxsize=128)
def _scaled_template(name: str, scale_key: int) -> np.ndarray | None:
    """Cache the scaled template by scale factor. scale_key = round(scale * 1000)."""
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
    """Find a template in frame and return the best match (coordinates relative to the frame origin)."""
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
    """Multi-target template matching with NMS deduplication."""
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


# ---------------------------------------------------------------- Color detection


def is_orange_option(img: np.ndarray, ratio_threshold: float = 0.06) -> bool:
    """BetterGI logic: if the proportion of orange text exceeds the threshold, treat it as a key-story option."""
    if img.size == 0:
        return False
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([11, 120, 120]), np.array([34, 255, 255]))
    return float(np.count_nonzero(mask)) / mask.size > ratio_threshold


def black_ratio(frame: np.ndarray, low: int = 0, high: int = 40) -> float:
    """Ratio of black pixels in the middle 1/3 region, used for black-screen cinematic detection."""
    h, w = frame.shape[:2]
    mid = frame[h // 3 : h * 2 // 3, :]
    gray = cv2.cvtColor(mid, cv2.COLOR_BGR2GRAY)
    mask = cv2.inRange(gray, low, high)
    return float(np.count_nonzero(mask)) / mask.size


def frame_diff_ratio(a: np.ndarray | None, b: np.ndarray | None, thresh: int = 12) -> float:
    """Frame-to-frame difference ratio, used to judge whether the screen is static (waiting)."""
    if a is None or b is None or a.shape != b.shape:
        return 1.0
    ga = cv2.cvtColor(cv2.resize(a, (192, 108)), cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(cv2.resize(b, (192, 108)), cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(ga, gb)
    return float(np.count_nonzero(diff > thresh)) / diff.size


# ---------------------------------------------------------------- OCR


class OcrEngine:
    """Lazy-initialized RapidOCR wrapper that degrades to empty results when unavailable.

    Two package generations are supported transparently:
      - ``rapidocr`` >= 3.x        : ``from rapidocr import RapidOCR``; the constructor accepts a
        ``lang=`` argument for multilingual recognition.
      - ``rapidocr-onnxruntime``   : the legacy package (Python < 3.13 only); it returns a
        (results, elapsed) tuple and has no ``lang=`` parameter, so non-Chinese languages are unavailable.
    """

    def __init__(self, lang: str = "ch") -> None:
        self._lang = lang
        self._engine = None
        self._available: bool | None = None

    def _ensure(self) -> bool:
        """Import and construct the OCR engine on first use; cache the availability result."""
        if self._available is not None:
            return self._available

        last_err: Exception | None = None
        for module, label in (("rapidocr", "rapidocr"), ("rapidocr_onnxruntime", "rapidocr-onnxruntime")):
            try:
                mod = __import__(module, fromlist=["RapidOCR"])
                # rapidocr 3.x honors lang=; the legacy package raises TypeError, so fall back to the
                # default (Chinese/English) model and warn when a non-Chinese language was requested.
                try:
                    self._engine = mod.RapidOCR(lang=self._lang)
                except TypeError:
                    if self._lang != "ch":
                        log.warning(
                            "the installed OCR package (%s) does not support the lang= argument; "
                            "falling back to the default Chinese/English model. "
                            "Upgrade to rapidocr>=3.0 to enable '%s' recognition.",
                            label, self._lang,
                        )
                    self._engine = mod.RapidOCR()
                self._available = True
                log.info("OCR engine loaded: %s (lang=%s)", label, self._lang)
                return True
            except Exception as exc:  # pragma: no cover - missing-dependency path
                last_err = exc

        log.error(
            "failed to load the OCR engine; option-text recognition falls back to positional tapping: %s\n"
            "  install with: pip install rapidocr onnxruntime",
            last_err,
        )
        self._available = False
        return False

    @staticmethod
    def _normalize(raw) -> list[tuple]:
        """Normalize both API generations into a list of ``(box, text, score)`` tuples."""
        if raw is None:
            return []

        # rapidocr >= 2.x: a RapidOCROutput dataclass exposing boxes / txts / scores.
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

        # Legacy package: a (results, elapsed) tuple. Unpack the first element and keep full rows.
        if isinstance(raw, tuple) and len(raw) == 2 and isinstance(raw[0], (list, type(None))):
            raw = raw[0] or []
        return [item for item in raw if item and len(item) >= 3]

    def recognize(self, img: np.ndarray, upscale: int | None = None) -> list[Match]:
        """Run OCR and return text boxes (``Match`` objects) with coordinates relative to ``img``.

        ``upscale``: integer upscaling factor for small option text. When omitted, the image is
        upscaled adaptively so a single text line reaches ~64px tall (capped at 4x to avoid noise).
        """
        if img.size == 0 or not self._ensure():
            return []
        # Option text lines are typically only 20~50px tall, below the OCR model's comfortable
        # training scale, so they get missed. Upscale small images so a line is >= 64px; cap at 4x
        # because further scaling only adds jaggies.
        if upscale:
            scale = float(upscale)
        else:
            h = img.shape[0]
            scale = max(1.0, min(4.0, 64.0 / h)) if h < 64 else 1.0
        src = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR) if scale != 1.0 else img
        try:
            raw = self._engine(src)
        except Exception as exc:  # pragma: no cover
            log.warning("OCR recognition failed: %s", exc)
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
