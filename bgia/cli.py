"""Command-line entry point for story, interaction, and reactive map tasks."""

from __future__ import annotations

import argparse
import logging
import math
import sys

from .adb import AdbDevice, AdbError
from .autoskip import AutoSkipTask
from .config import Config
from .game import GENSHIN_PACKAGES, detect_package, resolve_window
from .i18n import get_ocr_lang

log = logging.getLogger("bgia")


def _timeout_seconds(value: str) -> float:
    """Argparse converter for finite task timeouts."""

    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be a number") from exc
    if not math.isfinite(parsed) or not 0.05 <= parsed <= 300.0:
        raise argparse.ArgumentTypeError("timeout must be between 0.05 and 300 seconds")
    return parsed


def _panel_timeout_seconds(value: str) -> float:
    parsed = _timeout_seconds(value)
    if parsed > 60.0:
        raise argparse.ArgumentTypeError("panel timeout cannot exceed 60 seconds")
    return parsed


def _positive_index(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("candidate index must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("candidate index must be at least 1")
    return parsed


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _add_common_arguments(parser: argparse.ArgumentParser, *, suppressed: bool = False) -> None:
    """Add options accepted both before and after a subcommand."""

    default = argparse.SUPPRESS if suppressed else None
    parser.add_argument("-c", "--config", default=default, help="path to config file (YAML)")
    parser.add_argument("-s", "--serial", default=default, help="device serial number, required when multiple devices are connected")
    parser.add_argument("-w", "--wireless", default=default, help="wireless connection address, e.g. 192.168.1.20:5555")
    parser.add_argument("-p", "--package", default=default, help="force a specific game package name")
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        default=default,
        help="local mode: run directly inside a rooted Android shell (no adb needed)",
    )
    parser.add_argument("-i", "--interval", type=float, default=default, help="main loop interval (seconds)")
    parser.add_argument(
        "-m",
        "--option-mode",
        choices=["first", "second", "last", "random", "none"],
        default=default,
        help="dialogue-option selection strategy",
    )
    parser.add_argument(
        "-L",
        "--lang",
        default=default,
        help="game language, e.g. zh-CN/en/ja/ko/ru/fr/de/es/pt/it/tr/id/vi/th/zh-TW",
    )
    parser.add_argument("--debug", action="store_true", default=default, help="enable debug screenshots")
    parser.add_argument("-v", "--verbose", action="store_true", default=False if not suppressed else argparse.SUPPRESS, help="verbose logging")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bgia",
        description="ADB-based visual-capture auto story-skip script for Genshin Impact (ported from BetterGI AutoSkip)",
    )
    _add_common_arguments(p)
    sub = p.add_subparsers(dest="command")

    for name, help_text in (
        ("devices", "list connected devices"),
        ("check", "check environment and window detection result"),
        ("run", "start auto story-skip (default command)"),
    ):
        command_parser = sub.add_parser(name, help=help_text)
        _add_common_arguments(command_parser, suppressed=True)

    quick = sub.add_parser(
        "quick-teleport",
        help="confirm a currently visible map waypoint; does not navigate the map",
        description=(
            "Inspect an already-open map and an already-visible waypoint panel/list. "
            "This command never pans, zooms, or navigates the map. BetterGI desktop templates "
            "are recognition-only by default because native Android/cloud rendering is unverified."
        ),
    )
    _add_common_arguments(quick, suppressed=True)
    quick.add_argument("--candidate-name", help="require an exact normalized OCR name match")
    quick.add_argument(
        "--candidate-type",
        choices=[
            "TeleportWaypoint", "StatueOfTheSeven", "Domain", "Domain2",
            "ObsidianTotemPole", "PortableWaypoint", "Mansion", "SubSpaceWaypoint",
            "NodKraiMeetingPoint", "TabletOfTona",
        ],
        help="filter visible rows by BetterGI waypoint icon type",
    )
    quick.add_argument("--candidate-index", type=_positive_index, help="one-based row index after name/type filtering")
    quick.add_argument("--timeout", type=_timeout_seconds, default=15.0, help="overall timeout in seconds (maximum 300)")
    quick.add_argument("--panel-timeout", type=_panel_timeout_seconds, default=3.0, help="wait for the Teleport button after selecting a candidate")
    quick_mode = quick.add_mutually_exclusive_group()
    quick_mode.add_argument("--dry-run", dest="dry_run", action="store_true", help="recognize and report without sending taps (default)")
    quick_mode.add_argument(
        "--allow-unverified-ui",
        dest="dry_run",
        action="store_false",
        help="experimentally tap using unverified desktop-derived templates",
    )
    quick.set_defaults(dry_run=True)

    interact = sub.add_parser(
        "interact",
        help="observe exact right-side OCR text; experimental tap requires explicit opt-in",
        description=(
            "Observe exact normalized text in a bounded right-side ROI. No native-Android "
            "interaction-button anchor is packaged yet, so recognition is the default and live "
            "OCR-box tapping is explicitly experimental."
        ),
    )
    _add_common_arguments(interact, suppressed=True)
    interact.add_argument("--name", action="append", required=True, help="prompt text; repeat for aliases")
    interact.add_argument("--timeout", type=_timeout_seconds, default=15.0, help="wait timeout in seconds (maximum 300)")
    interact_mode = interact.add_mutually_exclusive_group()
    interact_mode.add_argument("--dry-run", dest="dry_run", action="store_true", help="recognize and report without tapping (default)")
    interact_mode.add_argument(
        "--allow-unverified-tap",
        dest="dry_run",
        action="store_false",
        help="experimentally tap the stable OCR box without a verified interaction anchor",
    )
    interact.set_defaults(dry_run=True)

    guild = sub.add_parser(
        "guild-assist",
        help="observe a guild prompt when already near Katheryne; experimental taps are opt-in",
        description=(
            "The player must already stand near Katheryne. By default this command only confirms "
            "the localized name across stable OCR frames. Experimental tapping additionally "
            "requires Talk-state and option-bubble gates; it does not verify reward collection."
        ),
    )
    _add_common_arguments(guild, suppressed=True)
    guild.add_argument("--action", choices=["daily", "expedition"], required=True)
    guild.add_argument("--timeout", type=_timeout_seconds, default=20.0, help="timeout for each recognition stage (maximum 300)")
    guild.add_argument("--katheryne-name", help="override the localized interaction-prompt name")
    guild.add_argument("--option-text", help="override the localized dialogue-option text")
    guild_mode = guild.add_mutually_exclusive_group()
    guild_mode.add_argument("--dry-run", dest="dry_run", action="store_true", help="recognize Katheryne without tapping (default)")
    guild_mode.add_argument(
        "--allow-unverified-tap",
        dest="dry_run",
        action="store_false",
        help="experimentally tap the OCR prompt and requested option",
    )
    guild.set_defaults(dry_run=True)
    return p


def merge_args(cfg: Config, args: argparse.Namespace) -> Config:
    # Priority is defaults < YAML < environment < CLI.
    cfg = Config._apply_env(cfg)
    for key in ("serial", "wireless", "package", "interval", "option_mode", "local"):
        val = getattr(args, key, None)
        if val is not None:
            setattr(cfg, key, val)
    lang = getattr(args, "lang", None)
    if lang is not None:
        cfg.apply_language(lang)
    if getattr(args, "debug", False):
        cfg.debug = True
    return cfg.validate()


def connect(cfg: Config) -> AdbDevice:
    # Local mode: run directly inside a rooted Android shell
    if cfg.local:
        dev = AdbDevice(local=True, adb_path=cfg.adb_path)
        if not dev.run("echo", "ok", timeout=5):
            raise AdbError("Local-mode init failed; make sure this runs inside a rooted shell")
        log.info("Local mode enabled (running directly in rooted Android shell)")
        # Verify that screencap / input are available
        try:
            dev.screencap()
            log.info("Local screenshot check passed")
        except AdbError as exc:
            raise AdbError(f"Local screenshot unavailable; make sure the device is rooted and screencap is reachable: {exc}")
        return dev

    if cfg.wireless:
        serial = AdbDevice.connect_wireless(cfg.wireless, cfg.adb_path)
        cfg.serial = cfg.serial or serial

    devices = [d for d in AdbDevice.list_devices(cfg.adb_path) if d[1] == "device"]
    if not devices:
        raise AdbError("No authorized device detected. Enable USB debugging and allow the debugging authorization on the phone")
    if cfg.serial is None:
        if len(devices) > 1:
            names = ", ".join(d[0] for d in devices)
            raise AdbError(f"Multiple devices detected, specify one with -s: {names}")
        cfg.serial = devices[0][0]

    dev = AdbDevice(serial=cfg.serial, adb_path=cfg.adb_path)
    dev.wait_ready()
    log.info("connected device: %s", dev.serial)
    return dev


def cmd_devices(cfg: Config) -> int:
    if cfg.local:
        devs = AdbDevice.list_devices(local=True)
        if devs:
            print("Local mode (rooted Android shell):")
            for serial, state in devs:
                print(f"{serial:<32} {state}")
        else:
            print("Local mode: no rooted environment detected. Make sure this runs inside a rooted shell (screencap available).")
        return 0
    devices = AdbDevice.list_devices(cfg.adb_path)
    if not devices:
        print("No device detected. Please confirm:")
        print("  1. USB debugging is enabled under Developer Options")
        print("  2. You tapped 'Allow' on the phone after connecting over USB")
        print("  3. For wireless debugging, run first: adb connect <IP>:<port>")
        return 1
    print(f"{'SERIAL':<32} STATE")
    for serial, state in devices:
        print(f"{serial:<32} {state}")
    return 0


def cmd_check(cfg: Config) -> int:
    dev = connect(cfg)

    disp = dev.get_display()
    print(f"Screen resolution: {disp.width}x{disp.height}  rotation={disp.rotation}")
    if disp.rotation not in (1, 3):
        print("  [WARN] device is not in landscape; Genshin should be in landscape, make sure the game is in the foreground")

    pkg = cfg.package or detect_package(dev)
    if pkg:
        name = next((k for k, v in GENSHIN_PACKAGES.items() if v == pkg), "unknown")
        print(f"Game package : {pkg}  ({name})")
    else:
        print("Game package : no Genshin process detected; launch the game and bring it to the foreground first")

    frame = dev.screencap()
    print(f"Screenshot   : {frame.shape[1]}x{frame.shape[0]}")

    win = resolve_window(dev, frame, pkg)
    print(f"Render region: x={win.x} y={win.y} w={win.width} h={win.height}")
    print(f"Scale factor : {win.scale:.4f} (relative to 1920x1080)")

    from .teleport import missing_quick_teleport_assets
    from .vision import ASSETS_DIR, OcrEngine

    required = ("disabled_ui.png", "icon_option.png", "icon_exclamation.png")
    optional = (
        "stop_auto.png",
        "hangout_skip.png",
        "page_close.png",
        "icon_click_continue.png",
        "icon_gear_option.png",
        "icon_gear_option_ctx.png",
    )
    required_missing = [name for name in required if not (ASSETS_DIR / name).exists()]
    optional_missing = [name for name in optional if not (ASSETS_DIR / name).exists()]
    print("Story assets : " + ("ready" if not required_missing else "[MISSING] " + ", ".join(required_missing)))
    print("Optional     : " + ("ready" if not optional_missing else "missing " + ", ".join(optional_missing)))
    teleport_missing = missing_quick_teleport_assets()
    print("Teleport UI : " + ("ready" if not teleport_missing else "[MISSING] " + ", ".join(teleport_missing)))

    print("OCR engine  : " + ("ready" if OcrEngine(lang=get_ocr_lang(cfg.lang))._ensure() else "unavailable (text recognition will degrade)"))
    return 0


def cmd_run(cfg: Config) -> int:
    dev = connect(cfg)
    disp = dev.get_display()
    if disp.rotation not in (1, 3):
        log.warning("device is not in landscape; switch to it if the game is not in the foreground")

    task = AutoSkipTask(dev, cfg)
    try:
        task.run()
    except KeyboardInterrupt:
        log.info("manually stopped")
    return 0


def cmd_quick_teleport(cfg: Config, args: argparse.Namespace) -> int:
    from .teleport import QuickTeleportStatus, QuickTeleportTask

    dev = connect(cfg)
    dev.get_display()
    result = QuickTeleportTask(dev, cfg).run(
        candidate_name=args.candidate_name,
        candidate_type=args.candidate_type,
        candidate_index=args.candidate_index,
        timeout=args.timeout,
        panel_timeout=args.panel_timeout,
        dry_run=args.dry_run,
    )
    print(f"QuickTeleport: {result.status.value}: {result.message}")
    if result.candidate is not None:
        print(
            f"Candidate    : {result.candidate.text} "
            f"({result.candidate.icon_type}, click={result.candidate.click})"
        )
    return 0 if result.status in {QuickTeleportStatus.MAP_CLOSED, QuickTeleportStatus.DRY_RUN} else 1


def cmd_interact(cfg: Config, args: argparse.Namespace) -> int:
    from .interaction import InteractionPromptTask

    dev = connect(cfg)
    dev.get_display()
    found = InteractionPromptTask(dev, cfg).wait(
        args.name,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )
    if found is None:
        print("Right-side text target not found before timeout")
        return 1
    print(f"Right-side text  : {found.text!r} matched {found.target!r}")
    if args.dry_run:
        print("Recognition only  : no tap was sent (default safe mode)")
    else:
        print("Experimental tap  : sent to an unverified OCR box")
    return 0


def cmd_guild_assist(cfg: Config, args: argparse.Namespace) -> int:
    from .guild import GuildAction, GuildAssistant

    dev = connect(cfg)
    dev.get_display()
    result = GuildAssistant(dev, cfg).run(
        GuildAction(args.action),
        timeout=args.timeout,
        dry_run=args.dry_run,
        katheryne_name=args.katheryne_name,
        option_text=args.option_text,
    )
    if result is None:
        print("Guild prompt or requested orange option was not found before timeout")
        return 1
    print(f"Guild prompt : {result.prompt_text!r}")
    if result.option_text:
        print(f"Guild option : {result.option_text!r}")
    if result.dry_run:
        print("Recognition  : stable Katheryne text confirmed; no tap was sent")
    elif result.option_text:
        print("Tap status   : option tap sent; selection/reward completion was not verified")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(getattr(args, "verbose", False))

    try:
        cfg = merge_args(Config.load(getattr(args, "config", None)), args)
        command = args.command or "run"
        if command == "devices":
            return cmd_devices(cfg)
        if command == "check":
            return cmd_check(cfg)
        if command == "quick-teleport":
            return cmd_quick_teleport(cfg, args)
        if command == "interact":
            return cmd_interact(cfg, args)
        if command == "guild-assist":
            return cmd_guild_assist(cfg, args)
        return cmd_run(cfg)
    except AdbError as exc:
        log.error("%s", exc)
        return 2
    except Exception as exc:
        log.error("runtime failure: %s", exc, exc_info=getattr(args, "verbose", False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
