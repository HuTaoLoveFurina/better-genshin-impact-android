"""Command-line entry point exposing the run / check / grab / teleport sub-commands."""

from __future__ import annotations

import argparse
import logging
import sys

from .adb import AdbDevice, AdbError
from .autoskip import AutoSkipTask
from .config import Config
from .game import GENSHIN_PACKAGES, detect_package, resolve_window

log = logging.getLogger("bgia")


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bgia",
        description="ADB-based visual-capture auto story-skip script for Genshin Impact (ported from BetterGI AutoSkip)",
    )
    sub = p.add_subparsers(dest="command")

    p.add_argument("-c", "--config", help="path to config file (YAML)")
    p.add_argument("-s", "--serial", help="device serial number, required when multiple devices are connected")
    p.add_argument("-w", "--wireless", help="wireless connection address, e.g. 192.168.1.20:5555")
    p.add_argument("-p", "--package", help="force a specific game package name")
    p.add_argument("-l", "--local", action="store_true",
                   help="local mode: run directly inside a rooted Android shell (no adb needed)")
    p.add_argument("-i", "--interval", type=float, help="main loop interval (seconds)")
    p.add_argument(
        "-m", "--option-mode",
        choices=["first", "second", "last", "random", "none"],
        help="dialogue-option selection strategy",
    )
    p.add_argument(
        "-L", "--lang",
        help="game language (overrides config lang), e.g. zh-CN/en/ja/ko/ru/fr/de/es/pt/it/tr/id/vi/th/zh-TW",
    )
    p.add_argument("--debug", action="store_true", help="enable debug screenshots")
    p.add_argument("-v", "--verbose", action="store_true", help="verbose logging")

    sub.add_parser("devices", help="list connected devices")
    sub.add_parser("check", help="check environment and window detection result")
    sub.add_parser("run", help="start auto story-skip (default command)")
    return p


def merge_args(cfg: Config, args: argparse.Namespace) -> Config:
    for key in ("serial", "wireless", "package", "interval", "option_mode", "local", "lang"):
        val = getattr(args, key, None)
        if val is not None:
            setattr(cfg, key, val)
    if args.debug:
        cfg.debug = True
    # Environment-variable overrides (priority: CLI args > env vars > YAML/defaults)
    cfg = Config._apply_env(cfg)
    return cfg


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

    from .vision import ASSETS_DIR, OcrEngine

    missing = [n for n in ("icon_option.png", "icon_exclamation.png", "stop_auto.png")
               if not (ASSETS_DIR / n).exists()]
    if missing:
        print(f"Templates   : [MISSING] {', '.join(missing)}")
        print(f"             place templates into {ASSETS_DIR}")
    else:
        print("Templates   : ready")

    print("OCR engine  : " + ("ready" if OcrEngine(lang=cfg.lang)._ensure() else "unavailable (option-text recognition will degrade)"))
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    cfg = merge_args(Config.load(args.config), args)

    try:
        command = args.command or "run"
        if command == "devices":
            return cmd_devices(cfg)
        if command == "check":
            return cmd_check(cfg)
        return cmd_run(cfg)
    except AdbError as exc:
        log.error("%s", exc)
        return 2
    except Exception as exc:
        log.error("runtime failure: %s", exc, exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())
