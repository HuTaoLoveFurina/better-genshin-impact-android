"""Dialogue-state detection shared by story automation tasks.

The current BetterGI implementation treats ``disabled_ui.png`` as the primary
evidence that a dialogue is active.  Android builds and cloud streams can still
expose the older auto-play button, so this port keeps the legacy template and
OCR checks as compatibility fallbacks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import numpy as np

from .vision import OcrEngine, match_template


class TalkEvidence(str, Enum):
    """The strongest visual signal observed for the current frame."""

    DISABLED_UI = "disabled_ui"
    LEGACY_STOP_AUTO = "legacy_stop_auto"
    LEGACY_PLAYING_OCR = "legacy_playing_ocr"
    NONE = "none"


@dataclass(frozen=True)
class TalkState:
    """Dialogue activity and the post-dialogue grace state."""

    active: bool
    in_grace: bool
    evidence: TalkEvidence


class TalkStateDetector:
    """Detect active dialogue without coupling recognition to click behavior."""

    def __init__(
        self,
        ocr: OcrEngine,
        playing_words: list[str],
        *,
        threshold: float = 0.8,
        grace_seconds: float = 10.0,
        legacy_fallback: bool = True,
        ocr_min_score: float = 0.75,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ocr = ocr
        self.playing_words = [word.casefold() for word in playing_words if word]
        self.threshold = threshold
        self.grace_seconds = max(0.0, grace_seconds)
        self.legacy_fallback = legacy_fallback
        self.ocr_min_score = ocr_min_score
        self._clock = clock
        self._last_active_at: float | None = None

    def reset(self) -> None:
        """Forget previous dialogue activity and clear the grace window."""

        self._last_active_at = None

    def _match(
        self,
        frame: np.ndarray,
        name: str,
        scale: float,
        roi: tuple[int, int, int, int],
    ) -> bool:
        return match_template(frame, name, scale, self.threshold, roi) is not None

    def detect_active(self, frame: np.ndarray, scale: float) -> TalkEvidence:
        """Return the strongest active-dialogue evidence for one frame."""

        height, width = frame.shape[:2]
        primary_roi = (0, 0, width // 3, height // 8)
        if self._match(frame, "disabled_ui.png", scale, primary_roi):
            return TalkEvidence.DISABLED_UI

        if not self.legacy_fallback:
            return TalkEvidence.NONE

        legacy_roi = (0, 0, width // 5, height // 8)
        if self._match(frame, "stop_auto.png", scale, legacy_roi):
            return TalkEvidence.LEGACY_STOP_AUTO

        tx, ty = int(round(60 * scale)), int(round(25 * scale))
        tw, th = int(round(180 * scale)), int(round(50 * scale))
        crop = frame[ty : ty + th, tx : tx + tw]
        if crop.size == 0:
            return TalkEvidence.NONE
        for result in self.ocr.recognize(crop):
            if result.score < self.ocr_min_score:
                continue
            text = result.text.casefold()
            if text and any(word in text for word in self.playing_words):
                return TalkEvidence.LEGACY_PLAYING_OCR
        return TalkEvidence.NONE

    def observe(
        self,
        frame: np.ndarray,
        scale: float,
        now: float | None = None,
    ) -> TalkState:
        """Observe a frame and update the monotonic post-dialogue grace window."""

        current = self._clock() if now is None else now
        evidence = self.detect_active(frame, scale)
        active = evidence is not TalkEvidence.NONE
        if active:
            self._last_active_at = current
        in_grace = active or (
            self._last_active_at is not None
            and current - self._last_active_at <= self.grace_seconds
        )
        return TalkState(active=active, in_grace=in_grace, evidence=evidence)
