"""Conservative Adventurers' Guild assistance for an already-nearby Katheryne.

This module deliberately does not claim BetterGI's full guild task. The Android
port currently lacks map localization and path following, so the caller must
stand near Katheryne first. Default mode observes stable name text; explicitly
experimental mode can send a Talk- and bubble-gated orange-option tap.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from .adb import AdbDevice
from .config import Config
from .interaction import InteractionPromptTask, OcrTextLocator, is_task_orange
from .i18n import get_guild_terms, get_keywords
from .talk_state import TalkEvidence, TalkStateDetector
from .vision import match_template_multi


class GuildAction(str, Enum):
    DAILY = "daily"
    EXPEDITION = "expedition"


@dataclass(frozen=True)
class GuildAssistResult:
    """Result of stable prompt observation or an unverified option-tap attempt."""

    prompt_text: str
    option_text: str
    dry_run: bool


class GuildAssistant:
    """Observe or experimentally tap one guild option without navigation automation."""

    def __init__(self, device: AdbDevice, config: Config) -> None:
        self.device = device
        self.config = config.validate()
        self.interaction = InteractionPromptTask(device, config)
        self.locator = OcrTextLocator(self.interaction.ocr)
        self.talk_detector = TalkStateDetector(
            self.interaction.ocr,
            get_keywords(config.lang).get("playing", []),
            threshold=config.template_threshold,
            grace_seconds=config.talk_grace_seconds,
            legacy_fallback=config.legacy_talk_detection,
        )

    @staticmethod
    def option_roi(frame) -> tuple[int, int, int, int]:
        height, width = frame.shape[:2]
        return (
            width // 2,
            height // 12,
            width - width // 2 - width // 6,
            height - height // 12 - 10,
        )

    def _anchored_option_roi(self, frame) -> tuple[int, int, int, int] | None:
        """Build BetterGI's text ROI only when a standard option bubble is visible."""

        assert self.interaction.window is not None
        bubbles = match_template_multi(
            frame,
            "icon_option.png",
            self.interaction.window.scale,
            self.config.template_threshold,
            self.option_roi(frame),
        )
        if not bubbles:
            return None
        lowest = max(bubbles, key=lambda match: match.y)
        scale = self.interaction.window.scale
        text_x = lowest.right + int(round(8 * scale))
        text_y = frame.shape[0] // 12
        text_width = int(round(535 * scale))
        text_height = lowest.bottom + int(round(30 * scale)) - text_y
        return text_x, text_y, text_width, max(0, text_height)

    def _wait_for_talk(self, timeout: float) -> bool:
        """Require two consecutive active-Talk frames after the prompt tap."""

        deadline = time.monotonic() + timeout
        active_frames = 0
        while time.monotonic() < deadline:
            frame = self.interaction.capture()
            assert self.interaction.window is not None
            evidence = self.talk_detector.detect_active(frame, self.interaction.window.scale)
            active_frames = active_frames + 1 if evidence is not TalkEvidence.NONE else 0
            if active_frames >= 2:
                return True
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(remaining, 0.25))
        return False

    def run(
        self,
        action: GuildAction,
        *,
        timeout: float = 20.0,
        dry_run: bool = True,
        katheryne_name: str | None = None,
        option_text: str | None = None,
    ) -> GuildAssistResult | None:
        timeout = Config._finite_float(timeout, "timeout", minimum=0.05, maximum=300.0)
        terms = get_guild_terms(self.config.lang)
        prompt_targets = [katheryne_name] if katheryne_name else terms.get("katheryne", [])
        option_targets = [option_text] if option_text else terms.get(action.value, [])
        if not prompt_targets or not option_targets:
            raise ValueError(
                "no verified guild localization is available for this language; "
                "provide --katheryne-name and --option-text explicitly"
            )

        prompt = self.interaction.wait(prompt_targets, timeout=timeout, dry_run=dry_run)
        if prompt is None:
            return None
        if dry_run:
            return GuildAssistResult(prompt.text, "", True)

        # The prompt tap is experimental because no native-Android interaction-button anchor is
        # packaged yet. Never inspect guild options unless the resulting Talk state is confirmed.
        if not self._wait_for_talk(timeout):
            return None

        deadline = time.monotonic() + timeout
        first_text_seen = False
        previous = None
        stable_frames = 0
        while time.monotonic() < deadline:
            frame = self.interaction.capture()
            assert self.interaction.window is not None
            if self.talk_detector.detect_active(frame, self.interaction.window.scale) is TalkEvidence.NONE:
                previous = None
                stable_frames = 0
                time.sleep(0.25)
                continue
            roi = self._anchored_option_roi(frame)
            if roi is None:
                previous = None
                stable_frames = 0
                time.sleep(0.25)
                continue
            option = self.locator.find(
                frame,
                option_targets,
                roi,
                upscale=2,
                exact=False,
                min_score=0.75,
                reject_ambiguous=True,
            )
            if option is None:
                previous = None
                stable_frames = 0
                time.sleep(0.25)
                continue
            # BetterGI re-reads the first visible option after a short stabilization delay.
            if not first_text_seen:
                first_text_seen = True
                time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
                previous = None
                stable_frames = 0
                continue
            if not is_task_orange(frame, option.match):
                previous = None
                stable_frames = 0
                time.sleep(0.25)
                continue
            if previous is not None and InteractionPromptTask._is_stable(previous, option):
                stable_frames += 1
            else:
                stable_frames = 1
            previous = option
            if stable_frames < 2:
                time.sleep(0.25)
                continue
            if time.monotonic() >= deadline:
                return None
            assert self.interaction.window is not None
            x, y = self.interaction.window.to_screen(*option.match.center)
            self.device.tap(x, y)
            time.sleep(self.config.click_delay)
            return GuildAssistResult(prompt.text, option.text, False)
        return None
