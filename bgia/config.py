"""Configuration loading: built-in defaults with optional overrides from a YAML file."""

from __future__ import annotations

import logging
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

    # Thresholds
    template_threshold: float = 0.80
    # Black-screen check: only treat as a "black-screen cinematic" (and tap to advance) when nearly fully black.
    # Note: cloud-Genshin / Genshin dark-story backgrounds can also be dim; too-low a threshold mis-triggers,
    # so by default the screen must be >= 92% near-black to count as a black screen.
    black_ratio_min: float = 0.92
    black_ratio_max: float = 0.999
    orange_ratio: float = 0.06

    # Debug
    debug: bool = False
    debug_dir: str = "debug"

    @classmethod
    def load(cls, path: str | Path | None) -> "Config":
        cfg = cls()
        if not path:
            return cfg
        p = Path(path)
        if not p.exists():
            log.warning("config file not found, using defaults: %s", p)
            return cfg

        import yaml

        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # First fill keyword defaults by language (used when the user did not override explicitly)
        lang = str(data.get("lang", DEFAULT_LANG))
        if lang not in SUPPORTED_GAME_LANGS:
            log.warning("unknown language '%s', falling back to %s (options: %s)",
                        lang, DEFAULT_LANG, "/".join(SUPPORTED_GAME_LANGS))
            lang = DEFAULT_LANG
        cfg.lang = lang
        kw = get_keywords(lang)
        cfg.select_keywords = list(kw.get("option", []))
        cfg.pause_keywords = list(kw.get("pause", []))

        valid = {f.name for f in fields(cls)}
        for k, v in data.items():
            if k in valid:
                setattr(cfg, k, v)
            else:
                log.warning("ignoring unknown config key: %s", k)
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
