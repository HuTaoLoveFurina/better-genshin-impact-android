"""Configuration loading: built-in defaults with optional overrides from a YAML file."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, fields
from pathlib import Path

from .i18n import SUPPORTED_GAME_LANGS, get_keywords

log = logging.getLogger(__name__)

# Default game language (Genshin client language code)
DEFAULT_LANG: str = "zh-CN"

# Built-in priority-selection keywords (Chinese fallback); a containing match is clicked first
DEFAULT_SELECT_KEYWORDS: list[str] = [
    "进入秘境", "领取奖励", "接受", "确认", "继续", "好的",
]

# Options not auto-clicked by default (consumable / irreversible actions); a hit pauses for manual handling
DEFAULT_PAUSE_KEYWORDS: list[str] = [
    "退出秘境", "秘境退出", "结束秘境", "放弃", "离开", "结算",
    "购买", "消耗", "兑换", "商店", "传送",
]


@dataclass
class Config:
    # Connection
    serial: str | None = None
    wireless: str | None = None
    adb_path: str = "adb"
    local: bool = False             # True = run locally in a rooted Android shell (no adb needed)
    package: str | None = None

    # Language
    lang: str = DEFAULT_LANG         # Genshin client language code (see bgia/i18n.py)

    # Loop
    interval: float = 0.6            # main loop interval (seconds)
    click_delay: float = 0.15        # wait after each tap (seconds)

    # Dialogue options
    choose_option: bool = True
    option_mode: str = "first"       # first / second / last / random / none
    before_choose_delay: float = 0.0 # extra wait before clicking an option (seconds), leaves time for voice
    custom_priority: list[str] = field(default_factory=list)
    select_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_SELECT_KEYWORDS))
    pause_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_PAUSE_KEYWORDS))
    prefer_orange: bool = False      # prefer orange (key-story) options; the orange tint is hard to detect reliably when the image is re-encoded by screen mirroring/streaming, so this is off by default

    # Behavior switches
    quick_skip: bool = True          # rapid tap to advance dialogue
    click_black_screen: bool = True  # tap during black-screen cinematics
    auto_hangout_skip: bool = True   # auto-click skip on hangout screens
    close_popup: bool = True         # close pop-up pages
    click_continue: bool = True       # auto-advance "tap anywhere to continue" prompts (e.g. Fontaine main story)

    # Dialogue-state detection
    talk_grace_seconds: float = 10.0  # keep safe post-dialogue handlers active for this duration
    legacy_talk_detection: bool = True  # retain stop_auto/OCR fallbacks for Android and cloud clients

    # Thresholds
    template_threshold: float = 0.80
    quick_teleport_threshold: float = 0.80  # independent minimum-confidence gate for map templates
    # Black-screen check: only treat as a "black-screen cinematic" (and tap to advance) when nearly fully black.
    # Note: cloud-Genshin / Genshin dark-story backgrounds can also be dim; too-low a threshold mis-triggers,
    # so by default the screen must be >= 92% near-black to count as a black screen.
    black_ratio_min: float = 0.92
    black_ratio_max: float = 0.999
    orange_ratio: float = 0.06

    # Debug
    debug: bool = False
    debug_dir: str = "debug"

    # Internal provenance flags used when a CLI language override is applied.
    _select_keywords_explicit: bool = field(default=False, init=False, repr=False)
    _pause_keywords_explicit: bool = field(default=False, init=False, repr=False)

    def apply_language(self, lang: str) -> None:
        """Apply a game language and refresh only non-user-supplied keyword defaults."""

        if lang not in SUPPORTED_GAME_LANGS:
            log.warning(
                "unknown language '%s', falling back to %s (options: %s)",
                lang,
                DEFAULT_LANG,
                "/".join(SUPPORTED_GAME_LANGS),
            )
            lang = DEFAULT_LANG
        self.lang = lang
        keywords = get_keywords(lang)
        if not self._select_keywords_explicit:
            self.select_keywords = list(keywords.get("option", []))
        if not self._pause_keywords_explicit:
            self.pause_keywords = list(keywords.get("pause", []))

    @staticmethod
    def _finite_float(
        value: object,
        name: str,
        *,
        minimum: float,
        maximum: float,
    ) -> float:
        """Return a bounded finite float or raise a user-facing configuration error."""

        try:
            converted = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a number between {minimum} and {maximum}") from exc
        if not math.isfinite(converted) or not minimum <= converted <= maximum:
            raise ValueError(f"{name} must be a finite number between {minimum} and {maximum}")
        return converted

    def validate(self) -> "Config":
        """Normalize numeric values and reject unsafe or nonsensical configuration."""

        valid_modes = {"first", "second", "last", "random", "none"}
        if self.option_mode not in valid_modes:
            log.warning("invalid option_mode=%r; falling back to first", self.option_mode)
            self.option_mode = "first"

        self.interval = self._finite_float(self.interval, "interval", minimum=0.05, maximum=60.0)
        self.click_delay = self._finite_float(self.click_delay, "click_delay", minimum=0.0, maximum=60.0)
        self.before_choose_delay = self._finite_float(
            self.before_choose_delay,
            "before_choose_delay",
            minimum=0.0,
            maximum=600.0,
        )
        self.talk_grace_seconds = self._finite_float(
            self.talk_grace_seconds,
            "talk_grace_seconds",
            minimum=0.0,
            maximum=60.0,
        )
        self.template_threshold = self._finite_float(
            self.template_threshold,
            "template_threshold",
            minimum=0.50,
            maximum=1.0,
        )
        self.quick_teleport_threshold = self._finite_float(
            self.quick_teleport_threshold,
            "quick_teleport_threshold",
            minimum=0.75,
            maximum=1.0,
        )
        self.black_ratio_min = self._finite_float(
            self.black_ratio_min,
            "black_ratio_min",
            minimum=0.0,
            maximum=1.0,
        )
        self.black_ratio_max = self._finite_float(
            self.black_ratio_max,
            "black_ratio_max",
            minimum=0.0,
            maximum=1.0,
        )
        if self.black_ratio_min > self.black_ratio_max:
            raise ValueError("black_ratio_min cannot exceed black_ratio_max")
        self.orange_ratio = self._finite_float(
            self.orange_ratio,
            "orange_ratio",
            minimum=0.0,
            maximum=1.0,
        )
        return self

    @classmethod
    def load(cls, path: str | Path | None) -> "Config":
        cfg = cls()
        if not path:
            return cfg.validate()
        p = Path(path)
        if not p.exists():
            log.warning("config file not found, using defaults: %s", p)
            return cfg

        import yaml

        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError("the configuration root must be a YAML mapping")

        # First fill keyword defaults by language (used when the user did not override explicitly)
        lang = str(data.get("lang", DEFAULT_LANG))
        if lang not in SUPPORTED_GAME_LANGS:
            log.warning("unknown language '%s', falling back to %s (options: %s)",
                        lang, DEFAULT_LANG, "/".join(SUPPORTED_GAME_LANGS))
            lang = DEFAULT_LANG
        cfg.apply_language(lang)
        cfg._select_keywords_explicit = "select_keywords" in data
        cfg._pause_keywords_explicit = "pause_keywords" in data

        valid = {f.name for f in fields(cls) if f.init}
        for k, v in data.items():
            if k == "lang":
                continue
            if k in valid:
                setattr(cfg, k, v)
            else:
                log.warning("ignoring unknown config key: %s", k)
        cfg.validate()
        log.info("config loaded: %s (lang=%s)", p, cfg.lang)
        return cfg

    @classmethod
    def _apply_env(cls, cfg: "Config") -> "Config":
        """Environment-variable overrides: switch strategies in containers/CI without editing the config file."""
        env_mode = __import__("os").environ.get("BGIA_OPTION_MODE")
        if env_mode:
            valid = {"first", "second", "last", "random", "none"}
            if env_mode in valid:
                cfg.option_mode = env_mode
                log.info("env BGIA_OPTION_MODE=%s -> applied", env_mode)
            else:
                log.warning("env BGIA_OPTION_MODE=%r is invalid, ignored (options: %s)",
                            env_mode, "/".join(sorted(valid)))

        env_choose = __import__("os").environ.get("BGIA_CHOOSE_OPTION")
        if env_choose is not None:
            cfg.choose_option = env_choose.strip().lower() in ("1", "true", "yes", "on")
            log.info("env BGIA_CHOOSE_OPTION=%s -> choose_option=%s",
                     env_choose, cfg.choose_option)
        return cfg
