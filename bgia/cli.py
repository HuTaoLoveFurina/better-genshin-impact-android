"""命令行入口。"""

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
        description="基于 ADB 视觉捕捉的原神自动过剧情脚本（移植自 BetterGI AutoSkip）",
    )
    sub = p.add_subparsers(dest="command")

    p.add_argument("-c", "--config", help="配置文件路径 (YAML)")
    p.add_argument("-s", "--serial", help="设备序列号，多设备时必填")
    p.add_argument("-w", "--wireless", help="无线连接地址，如 192.168.1.20:5555")
    p.add_argument("-p", "--package", help="强制指定游戏包名")
    p.add_argument("-l", "--local", action="store_true",
                   help="本地模式：在已 root 的安卓 shell 中直接运行（无需 adb）")
    p.add_argument("-i", "--interval", type=float, help="主循环间隔（秒）")
    p.add_argument(
        "-m", "--option-mode",
        choices=["first", "second", "last", "random", "none"],
        help="选项策略",
    )
    p.add_argument("--debug", action="store_true", help="开启调试截图")
    p.add_argument("-v", "--verbose", action="store_true", help="详细日志")

    sub.add_parser("devices", help="列出已连接设备")
    sub.add_parser("check", help="检查环境与窗口识别结果")
    sub.add_parser("run", help="启动自动剧情（默认命令）")
    return p


def merge_args(cfg: Config, args: argparse.Namespace) -> Config:
    for key in ("serial", "wireless", "package", "interval", "option_mode", "local"):
        val = getattr(args, key, None)
        if val is not None:
            setattr(cfg, key, val)
    if args.debug:
        cfg.debug = True
    # 环境变量覆盖（优先级：命令行 > 环境变量 > YAML/默认）
    cfg = Config._apply_env(cfg)
    return cfg


def connect(cfg: Config) -> AdbDevice:
    # 本地模式：直接在已 root 的安卓 shell 中运行
    if cfg.local:
        dev = AdbDevice(local=True, adb_path=cfg.adb_path)
        if not dev.run("echo", "ok", timeout=5):
            raise AdbError("本地模式初始化失败，请确认已在 root shell 中运行")
        log.info("已启用本地模式（已 root 安卓 shell 直接执行）")
        # 校验 screencap / input 可用
        try:
            dev.screencap()
            log.info("本地截图验证通过")
        except AdbError as exc:
            raise AdbError(f"本地截图不可用，请确认已 root 且 screencap 可访问: {exc}")
        return dev

    if cfg.wireless:
        serial = AdbDevice.connect_wireless(cfg.wireless, cfg.adb_path)
        cfg.serial = cfg.serial or serial

    devices = [d for d in AdbDevice.list_devices(cfg.adb_path) if d[1] == "device"]
    if not devices:
        raise AdbError("未检测到已授权设备。请开启 USB 调试并在手机上允许调试授权")
    if cfg.serial is None:
        if len(devices) > 1:
            names = ", ".join(d[0] for d in devices)
            raise AdbError(f"检测到多台设备，请用 -s 指定: {names}")
        cfg.serial = devices[0][0]

    dev = AdbDevice(serial=cfg.serial, adb_path=cfg.adb_path)
    dev.wait_ready()
    log.info("已连接设备: %s", dev.serial)
    return dev


def cmd_devices(cfg: Config) -> int:
    if cfg.local:
        devs = AdbDevice.list_devices(local=True)
        if devs:
            print("本地模式 (已 root 安卓 shell):")
            for serial, state in devs:
                print(f"{serial:<32} {state}")
        else:
            print("本地模式未检测到 root 环境，请确认已在 root shell 中运行（screencap 可用）。")
        return 0
    devices = AdbDevice.list_devices(cfg.adb_path)
    if not devices:
        print("未检测到设备。请确认：")
        print("  1. 手机已开启【开发者选项 -> USB 调试】")
        print("  2. USB 连接后已在手机上点击【允许】")
        print("  3. 无线调试请先执行: adb connect <IP>:<端口>")
        return 1
    print(f"{'序列号':<32} 状态")
    for serial, state in devices:
        print(f"{serial:<32} {state}")
    return 0


def cmd_check(cfg: Config) -> int:
    dev = connect(cfg)

    disp = dev.get_display()
    print(f"屏幕分辨率 : {disp.width}x{disp.height}  rotation={disp.rotation}")
    if disp.rotation not in (1, 3):
        print("  [警告] 当前非横屏，原神应处于横屏状态，请确认游戏已在前台")

    pkg = cfg.package or detect_package(dev)
    if pkg:
        name = next((k for k, v in GENSHIN_PACKAGES.items() if v == pkg), "未知")
        print(f"游戏包名   : {pkg}  ({name})")
    else:
        print("游戏包名   : 未检测到原神进程，请先启动游戏并切到前台")

    frame = dev.screencap()
    print(f"截图尺寸   : {frame.shape[1]}x{frame.shape[0]}")

    win = resolve_window(dev, frame, pkg)
    print(f"渲染区域   : x={win.x} y={win.y} w={win.width} h={win.height}")
    print(f"缩放系数   : {win.scale:.4f} (相对 1920x1080)")

    from .vision import ASSETS_DIR, OcrEngine

    missing = [n for n in ("icon_option.png", "icon_exclamation.png", "stop_auto.png")
               if not (ASSETS_DIR / n).exists()]
    if missing:
        print(f"模板资源   : [缺失] {', '.join(missing)}")
        print(f"             请将模板放入 {ASSETS_DIR}")
    else:
        print("模板资源   : 就绪")

    print("OCR 引擎   : " + ("就绪" if OcrEngine()._ensure() else "不可用（选项文本识别将降级）"))
    return 0


def cmd_run(cfg: Config) -> int:
    dev = connect(cfg)
    disp = dev.get_display()
    if disp.rotation not in (1, 3):
        log.warning("当前设备非横屏，若游戏未在前台请先切换")

    task = AutoSkipTask(dev, cfg)
    try:
        task.run()
    except KeyboardInterrupt:
        log.info("已手动停止")
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
        log.error("运行失败: %s", exc, exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())
