#!/usr/bin/env python3
"""Import the GPL-compatible visual assets used by the Android port.

The script copies only the assets exercised by the current code. It does not
import BetterGI's map feature database, which would incorrectly imply support
for full coordinate-driven TpTask navigation.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "assets" / "1920x1080"

AUTOSKIP_ASSETS = (
    "disabled_ui.png",
    "hangout_skip.png",
    "page_close.png",
)

QUICK_TELEPORT_ASSETS = (
    "GoTeleport.png",
    "MapScaleButton.png",
    "MapSettingsButton.png",
    "MapCloseButton.png",
    "MapChoose.png",
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


def source_revision(source: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=source,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def copy_assets(source: Path, force: bool = False) -> list[Path]:
    autoskip_source = (
        source
        / "BetterGenshinImpact"
        / "GameTask"
        / "AutoSkip"
        / "Assets"
        / "1920x1080"
    )
    teleport_source = (
        source
        / "BetterGenshinImpact"
        / "GameTask"
        / "QuickTeleport"
        / "Assets"
        / "1920x1080"
    )
    teleport_destination = DESTINATION / "quick_teleport"
    teleport_destination.mkdir(parents=True, exist_ok=True)
    DESTINATION.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for name in AUTOSKIP_ASSETS:
        src = autoskip_source / name
        dst = DESTINATION / name
        if not src.is_file():
            raise FileNotFoundError(f"BetterGI asset not found: {src}")
        if force or not dst.exists():
            shutil.copy2(src, dst)
            copied.append(dst)

    for name in QUICK_TELEPORT_ASSETS:
        src = teleport_source / name
        dst = teleport_destination / name
        if not src.is_file():
            raise FileNotFoundError(f"BetterGI asset not found: {src}")
        if force or not dst.exists():
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="path to a BetterGI source checkout")
    parser.add_argument("--force", action="store_true", help="overwrite assets that already exist")
    args = parser.parse_args()

    source = args.source.resolve()
    copied = copy_assets(source, force=args.force)
    print(f"BetterGI revision: {source_revision(source)}")
    print(f"Imported {len(copied)} asset(s):")
    for path in copied:
        print(f"  {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
