"""Reactive map teleport confirmation for an already-visible waypoint.

This module intentionally implements only BetterGI's QuickTeleport layer.  It
does not pan the map, localize world coordinates, or execute a full ``TpTask``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np

from .adb import AdbDevice
from .config import Config
from .game import GameWindow, resolve_window
from .i18n import get_ocr_lang
from .interaction import normalize_ui_text
from .vision import ASSETS_DIR, Match, OcrEngine, match_template, match_template_multi


ASSET_PREFIX = "quick_teleport"
UI_ASSETS = (
    "GoTeleport.png",
    "MapScaleButton.png",
    "MapSettingsButton.png",
    "MapCloseButton.png",
    "MapChoose.png",
)
ICON_ASSETS = (
    "TeleportWaypoint.png",
    "StatueOfTheSeven.png",
    "Domain.png",
    "Domain2.png",
    "ObsidianTotemPole.png",
    "PortableWaypoint.png",
    "Mansion.png",
    "SubSpaceWaypoint.png",
    "NodKraiMeetingPoint.png",
    "TabletOfTona.png",
)


class QuickTeleportStatus(str, Enum):
    MAP_CLOSED = "map_closed"
    DRY_RUN = "dry_run"
    ASSET_MISSING = "asset_missing"
    NOT_IN_MAP = "not_in_map"
    NO_CANDIDATE = "no_candidate"
    TARGET_NOT_FOUND = "target_not_found"
    AMBIGUOUS_TARGET = "ambiguous_target"
    PANEL_TIMEOUT = "panel_timeout"
    MAP_EXIT_TIMEOUT = "map_exit_timeout"


@dataclass(frozen=True)
class MapCandidate:
    """One OCR-validated item from the map's overlapping-waypoint list."""

    icon_type: str
    icon: Match
    text: str
    click: tuple[int, int]


@dataclass(frozen=True)
class QuickTeleportResult:
    status: QuickTeleportStatus
    message: str
    candidate: MapCandidate | None = None


def missing_quick_teleport_assets() -> list[str]:
    """Return required QuickTeleport assets that are absent from the repository."""

    return [
        name
        for name in (*UI_ASSETS, *ICON_ASSETS)
        if not (ASSETS_DIR / ASSET_PREFIX / name).exists()
    ]


def _asset(name: str) -> str:
    return f"{ASSET_PREFIX}/{name}"


def _intersection_over_union(left: Match, right: Match) -> float:
    x0 = max(left.x, right.x)
    y0 = max(left.y, right.y)
    x1 = min(left.right, right.right)
    y1 = min(left.bottom, right.bottom)
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    if intersection == 0:
        return 0.0
    union = left.width * left.height + right.width * right.height - intersection
    return intersection / union if union else 0.0


class MapUiRecognizer:
    """Recognize the BetterGI-compatible map UI and its visible candidates."""

    def __init__(self, ocr: OcrEngine, threshold: float = 0.8) -> None:
        self.ocr = ocr
        self.threshold = threshold

    @staticmethod
    def candidate_roi(frame: np.ndarray, scale: float) -> tuple[int, int, int, int]:
        height = frame.shape[0]
        return (
            int(round(1270 * scale)),
            int(round(100 * scale)),
            int(round(50 * scale)),
            max(0, height - int(round(200 * scale))),
        )

    def _find(
        self,
        frame: np.ndarray,
        name: str,
        scale: float,
        roi: tuple[int, int, int, int],
    ) -> Match | None:
        return match_template(
            frame,
            _asset(name),
            scale,
            self.threshold,
            roi,
            grayscale=True,
        )

    def is_big_map(self, frame: np.ndarray, scale: float) -> bool:
        height, width = frame.shape[:2]
        scale_roi = (
            int(round(30 * scale)),
            int(round(440 * scale)),
            int(round(40 * scale)),
            int(round(200 * scale)),
        )
        settings_roi = (
            int(round(25 * scale)),
            max(0, height - int(round(90 * scale))),
            int(round(58 * scale)),
            int(round(62 * scale)),
        )
        return (
            self._find(frame, "MapScaleButton.png", scale, scale_roi) is not None
            or self._find(frame, "MapSettingsButton.png", scale, settings_roi) is not None
        )

    def teleport_button(self, frame: np.ndarray, scale: float) -> Match | None:
        height = frame.shape[0]
        roi = (
            int(round(1440 * scale)),
            max(0, height - int(round(120 * scale))),
            int(round(100 * scale)),
            int(round(120 * scale)),
        )
        return self._find(frame, "GoTeleport.png", scale, roi)

    def candidate_list_blocked(self, frame: np.ndarray, scale: float) -> bool:
        height, width = frame.shape[:2]
        close_roi = (
            max(0, width - int(round(107 * scale))),
            int(round(19 * scale)),
            int(round(58 * scale)),
            int(round(58 * scale)),
        )
        choose_roi = (
            max(0, width - int(round(480 * scale))),
            0,
            int(round(100 * scale)),
            int(round(70 * scale)),
        )
        return (
            self._find(frame, "MapCloseButton.png", scale, close_roi) is not None
            or self._find(frame, "MapChoose.png", scale, choose_roi) is not None
        )

    def _icon_matches(self, frame: np.ndarray, scale: float) -> list[tuple[str, Match]]:
        roi = self.candidate_roi(frame, scale)
        raw: list[tuple[str, Match]] = []
        for name in ICON_ASSETS:
            matches = match_template_multi(
                frame,
                _asset(name),
                scale,
                self.threshold,
                roi,
                max_count=10,
                grayscale=True,
            )
            raw.extend((name.removesuffix(".png"), match) for match in matches)

        # BetterGI deduplicates within each template only. Cross-template NMS prevents one icon
        # from being OCRed and clicked multiple times under different compatible templates.
        kept: list[tuple[str, Match]] = []
        for item in sorted(raw, key=lambda pair: pair[1].score, reverse=True):
            if all(_intersection_over_union(item[1], other[1]) < 0.5 for other in kept):
                kept.append(item)
        return sorted(kept, key=lambda pair: (pair[1].y, pair[1].x))

    def candidates(self, frame: np.ndarray, scale: float) -> list[MapCandidate]:
        found: list[MapCandidate] = []
        for icon_type, icon in self._icon_matches(frame, scale):
            text_x = icon.right
            text_y = max(0, icon.y - int(round(8 * scale)))
            text_width = int(round(200 * scale))
            text_height = icon.height + int(round(16 * scale))
            text_width = min(text_width, frame.shape[1] - text_x)
            text_height = min(text_height, frame.shape[0] - text_y)
            if text_width <= 0 or text_height <= 0:
                continue
            crop = frame[text_y : text_y + text_height, text_x : text_x + text_width]
            hls = cv2.cvtColor(crop, cv2.COLOR_BGR2HLS)
            white_text = cv2.inRange(
                hls,
                np.array([0, 245, 0]),
                np.array([180, 255, 15]),
            )
            text = " ".join(
                result.text.strip()
                for result in self.ocr.recognize(white_text, upscale=2)
                if result.text.strip() and result.score >= 0.75
            ).strip()
            if len(normalize_ui_text(text)) < 2:
                continue
            found.append(
                MapCandidate(
                    icon_type=icon_type,
                    icon=icon,
                    text=text,
                    click=(text_x + text_width // 2, icon.y + icon.height // 2),
                )
            )
        return found


class QuickTeleportTask:
    """Confirm a selected or visible map candidate without navigating the map."""

    def __init__(self, device: AdbDevice, config: Config) -> None:
        self.device = device
        self.config = config.validate()
        self.ocr = OcrEngine(lang=get_ocr_lang(config.lang))
        self.recognizer = MapUiRecognizer(self.ocr, config.quick_teleport_threshold)
        self.window: GameWindow | None = None

    def _capture(self) -> np.ndarray:
        frame_full = self.device.screencap()
        if self.window is None:
            self.window = resolve_window(self.device, frame_full, self.config.package)
        frame = self.window.crop(frame_full)
        if frame.size == 0:
            self.window = None
            raise RuntimeError("the detected game render region is empty")
        return frame

    def _tap(self, point: tuple[int, int]) -> None:
        assert self.window is not None
        x, y = self.window.to_screen(*point)
        self.device.tap(x, y)

    def run(
        self,
        *,
        candidate_name: str | None = None,
        candidate_type: str | None = None,
        candidate_index: int | None = None,
        timeout: float = 15.0,
        panel_timeout: float = 3.0,
        dry_run: bool = True,
    ) -> QuickTeleportResult:
        timeout = Config._finite_float(timeout, "timeout", minimum=0.05, maximum=300.0)
        panel_timeout = Config._finite_float(
            panel_timeout,
            "panel_timeout",
            minimum=0.05,
            maximum=60.0,
        )
        target = normalize_ui_text(candidate_name or "")
        if candidate_name is not None and len(target) < 2:
            raise ValueError("candidate_name must contain at least two normalized characters")
        valid_types = {name.removesuffix(".png") for name in ICON_ASSETS}
        if candidate_type is not None and candidate_type not in valid_types:
            raise ValueError("candidate_type must be one of: " + ", ".join(sorted(valid_types)))
        if candidate_index is not None:
            if isinstance(candidate_index, bool) or not isinstance(candidate_index, int) or candidate_index < 1:
                raise ValueError("candidate_index must be a positive one-based integer")

        missing = missing_quick_teleport_assets()
        if missing:
            return QuickTeleportResult(
                QuickTeleportStatus.ASSET_MISSING,
                "missing QuickTeleport assets: " + ", ".join(missing),
            )

        deadline = time.monotonic() + timeout
        requires_candidate_selection = bool(target or candidate_type or candidate_index is not None)
        selected: MapCandidate | None = None
        selected_at: float | None = None
        teleport_clicked = False
        saw_candidate = False
        saw_eligible_button = False
        previous_candidate: MapCandidate | None = None
        stable_candidate_frames = 0
        previous_button: Match | None = None
        stable_button_frames = 0
        map_absent_frames = 0

        while time.monotonic() <= deadline:
            frame = self._capture()
            scale = self.window.scale if self.window is not None else 1.0
            in_map = self.recognizer.is_big_map(frame, scale)
            if not in_map:
                if teleport_clicked:
                    map_absent_frames += 1
                    if map_absent_frames >= 2:
                        return QuickTeleportResult(
                            QuickTeleportStatus.MAP_CLOSED,
                            "the map was absent for two consecutive frames after the Teleport tap; landing was not verified",
                            selected,
                        )
                    time.sleep(0.1)
                    continue
                return QuickTeleportResult(
                    QuickTeleportStatus.NOT_IN_MAP,
                    "the BetterGI-compatible big-map UI was not detected",
                )
            map_absent_frames = 0

            if teleport_clicked:
                time.sleep(0.1)
                continue

            button = self.recognizer.teleport_button(frame, scale)
            if button is not None and (not requires_candidate_selection or selected is not None):
                saw_eligible_button = True
                if self._same_match(previous_button, button):
                    stable_button_frames += 1
                else:
                    stable_button_frames = 1
                previous_button = button
                if stable_button_frames < 2:
                    time.sleep(0.1)
                    continue
                if dry_run:
                    return QuickTeleportResult(
                        QuickTeleportStatus.DRY_RUN,
                        "Teleport button detected; no tap was sent",
                        selected,
                    )
                if time.monotonic() >= deadline:
                    break
                self._tap(button.center)
                teleport_clicked = True
                time.sleep(max(0.05, self.config.click_delay))
                continue
            previous_button = None
            stable_button_frames = 0

            if selected_at is not None:
                if time.monotonic() - selected_at > panel_timeout:
                    return QuickTeleportResult(
                        QuickTeleportStatus.PANEL_TIMEOUT,
                        "the Teleport button did not appear after selecting the candidate",
                        selected,
                    )
                time.sleep(0.1)
                continue

            if self.recognizer.candidate_list_blocked(frame, scale):
                time.sleep(0.1)
                continue

            candidates = self.recognizer.candidates(frame, scale)
            saw_candidate = saw_candidate or bool(candidates)
            if target:
                candidates = [
                    candidate
                    for candidate in candidates
                    if normalize_ui_text(candidate.text) == target
                ]
            if candidate_type:
                candidates = [candidate for candidate in candidates if candidate.icon_type == candidate_type]
            if not candidates:
                previous_candidate = None
                stable_candidate_frames = 0
                time.sleep(0.1)
                continue

            if candidate_index is not None:
                if candidate_index > len(candidates):
                    previous_candidate = None
                    stable_candidate_frames = 0
                    time.sleep(0.1)
                    continue
                candidates = [candidates[candidate_index - 1]]
            elif len(candidates) > 1:
                return QuickTeleportResult(
                    QuickTeleportStatus.AMBIGUOUS_TARGET,
                    f"{len(candidates)} visible candidates matched; specify --candidate-type or --candidate-index",
                )

            candidate = candidates[0]
            if self._same_candidate(previous_candidate, candidate):
                stable_candidate_frames += 1
            else:
                stable_candidate_frames = 1
            previous_candidate = candidate
            if stable_candidate_frames < 2:
                time.sleep(0.1)
                continue
            selected = candidate
            if dry_run:
                return QuickTeleportResult(
                    QuickTeleportStatus.DRY_RUN,
                    f"candidate detected: {selected.text}",
                    selected,
                )
            if time.monotonic() >= deadline:
                break
            time.sleep(0.2)
            if time.monotonic() >= deadline:
                break
            self._tap(selected.click)
            selected_at = time.monotonic()
            time.sleep(0.08)

        if teleport_clicked:
            return QuickTeleportResult(
                QuickTeleportStatus.MAP_EXIT_TIMEOUT,
                "the map remained visible after the Teleport button was pressed",
                selected,
            )
        if selected_at is not None or saw_eligible_button:
            return QuickTeleportResult(
                QuickTeleportStatus.PANEL_TIMEOUT,
                "the Teleport button did not remain stable before the overall timeout",
                selected,
            )
        if requires_candidate_selection and saw_candidate:
            return QuickTeleportResult(
                QuickTeleportStatus.TARGET_NOT_FOUND,
                "no visible candidate matched the requested name/type/index filters",
            )
        return QuickTeleportResult(
            QuickTeleportStatus.NO_CANDIDATE,
            "no OCR-valid waypoint candidate became visible before timeout",
        )

    @staticmethod
    def _same_candidate(previous: MapCandidate | None, current: MapCandidate) -> bool:
        """Require stable type, normalized text, and row position across captures."""

        if previous is None:
            return False
        if previous.icon_type != current.icon_type:
            return False
        if normalize_ui_text(previous.text) != normalize_ui_text(current.text):
            return False
        px, py = previous.click
        cx, cy = current.click
        return abs(px - cx) <= 24 and abs(py - cy) <= 24

    @staticmethod
    def _same_match(previous: Match | None, current: Match) -> bool:
        if previous is None:
            return False
        px, py = previous.center
        cx, cy = current.center
        return abs(px - cx) <= 24 and abs(py - cy) <= 24
