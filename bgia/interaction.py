"""Bounded right-side OCR observation with explicitly experimental tapping."""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np

from .adb import AdbDevice
from .config import Config
from .game import GameWindow, resolve_window
from .i18n import get_ocr_lang
from .vision import Match, OcrEngine


def normalize_ui_text(value: str) -> str:
    """Normalize OCR text for stable UI-name comparisons."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s\-‐‑‒–—―·•>＞]+", "", normalized)


@dataclass(frozen=True)
class LocatedText:
    """An OCR result with coordinates relative to the game render region."""

    text: str
    match: Match
    target: str


class OcrTextLocator:
    """Locate one of several explicit text targets inside a bounded ROI."""

    def __init__(self, ocr: OcrEngine) -> None:
        self.ocr = ocr

    def find(
        self,
        frame: np.ndarray,
        targets: Iterable[str],
        roi: tuple[int, int, int, int],
        *,
        upscale: int = 2,
        exact: bool = True,
        min_score: float = 0.75,
        minimum_target_length: int = 2,
        reject_ambiguous: bool = False,
    ) -> LocatedText | None:
        x0, y0, width, height = roi
        x0, y0 = max(0, x0), max(0, y0)
        width = min(width, frame.shape[1] - x0)
        height = min(height, frame.shape[0] - y0)
        if width <= 0 or height <= 0:
            return None
        crop = frame[y0 : y0 + height, x0 : x0 + width]
        normalized_targets = [
            (target, normalize_ui_text(target))
            for target in targets
            if len(normalize_ui_text(target)) >= minimum_target_length
        ]
        matches: list[LocatedText] = []
        for result in self.ocr.recognize(crop, upscale=upscale):
            if result.score < min_score:
                continue
            observed = normalize_ui_text(result.text)
            if not observed:
                continue
            for target, normalized_target in normalized_targets:
                matched = observed == normalized_target if exact else normalized_target in observed
                if matched:
                    matches.append(
                        LocatedText(
                            text=result.text,
                            target=target,
                            match=Match(
                                x=x0 + result.x,
                                y=y0 + result.y,
                                width=result.width,
                                height=result.height,
                                score=result.score,
                                text=result.text,
                            ),
                        )
                    )
                    break
        if reject_ambiguous and len(matches) != 1:
            return None
        return max(matches, key=lambda item: item.match.score, default=None)


class InteractionPromptTask:
    """Observe exact right-side OCR text, with experimental unverified tapping.

    The imported desktop assets do not include a verified native-Android interaction-button
    anchor. Recognition is therefore safe by default, while live tapping requires an explicit
    caller opt-in and remains unsuitable for unattended use.
    """

    def __init__(self, device: AdbDevice, config: Config) -> None:
        self.device = device
        self.config = config.validate()
        self.ocr = OcrEngine(lang=get_ocr_lang(config.lang))
        self.locator = OcrTextLocator(self.ocr)
        self.window: GameWindow | None = None

    @staticmethod
    def prompt_roi(frame: np.ndarray) -> tuple[int, int, int, int]:
        """Return the broad right-side candidate-text area used by Android clients."""

        height, width = frame.shape[:2]
        return (
            int(width * 0.52),
            int(height * 0.25),
            int(width * 0.43),
            int(height * 0.55),
        )

    def capture(self) -> np.ndarray:
        frame_full = self.device.screencap()
        if self.window is None:
            self.window = resolve_window(self.device, frame_full, self.config.package)
        frame = self.window.crop(frame_full)
        if frame.size == 0:
            self.window = None
            raise RuntimeError("the detected game render region is empty")
        return frame

    def wait(
        self,
        names: Iterable[str],
        *,
        timeout: float = 15.0,
        dry_run: bool = True,
        min_score: float = 0.75,
        confirmations: int = 2,
    ) -> LocatedText | None:
        """Wait for stable exact text and optionally tap its unverified OCR box."""

        timeout = Config._finite_float(timeout, "timeout", minimum=0.05, maximum=300.0)
        min_score = Config._finite_float(min_score, "min_score", minimum=0.5, maximum=1.0)
        confirmations = int(confirmations)
        if confirmations < 2:
            raise ValueError("confirmations must be at least 2")
        names = list(names)
        if not names or any(len(normalize_ui_text(name)) < 2 for name in names):
            raise ValueError("each interaction target must contain at least two normalized characters")

        deadline = time.monotonic() + timeout
        previous: LocatedText | None = None
        stable_frames = 0
        while time.monotonic() < deadline:
            frame = self.capture()
            found = self.locator.find(
                frame,
                names,
                self.prompt_roi(frame),
                upscale=2,
                exact=True,
                min_score=min_score,
                reject_ambiguous=True,
            )
            if found is not None:
                if previous is not None and self._is_stable(previous, found):
                    stable_frames += 1
                else:
                    stable_frames = 1
                previous = found
                if stable_frames >= confirmations:
                    if time.monotonic() >= deadline:
                        return None
                    if not dry_run:
                        assert self.window is not None
                        x, y = self.window.to_screen(*found.match.center)
                        self.device.tap(x, y)
                        time.sleep(self.config.click_delay)
                    return found
            else:
                previous = None
                stable_frames = 0
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(remaining, min(0.25, max(0.05, self.config.interval))))
        return None

    @staticmethod
    def _is_stable(previous: LocatedText, current: LocatedText) -> bool:
        """Return whether two observations identify the same text at a stable location."""

        if normalize_ui_text(previous.target) != normalize_ui_text(current.target):
            return False
        if normalize_ui_text(previous.text) != normalize_ui_text(current.text):
            return False
        px, py = previous.match.center
        cx, cy = current.match.center
        tolerance = max(
            24.0,
            previous.match.width * 0.75,
            previous.match.height * 0.75,
            current.match.width * 0.75,
            current.match.height * 0.75,
        )
        return (px - cx) ** 2 + (py - cy) ** 2 <= tolerance**2


def is_task_orange(frame: np.ndarray, match: Match, ratio_threshold: float = 0.1) -> bool:
    """Apply BetterGI's task-specific orange text threshold around an OCR box."""

    x0 = max(0, match.x - 8)
    y0 = max(0, match.y - 8)
    x1 = min(frame.shape[1], match.right + 8)
    y1 = min(frame.shape[0], match.bottom + 8)
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return False
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([10, 150, 150]), np.array([25, 255, 255]))
    return float(np.count_nonzero(mask)) / mask.size > ratio_threshold
