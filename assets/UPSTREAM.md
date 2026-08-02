# Upstream Visual Assets

The assets listed below are copied from
[BetterGI](https://github.com/babalae/better-genshin-impact) under the same
GPL-3.0 license as this repository.

Import baseline:

- Repository revision: `b0c8fca19577fce0b6bdd38ec9fe2cd81babeb20`
- BetterGI directories:
  - `BetterGenshinImpact/GameTask/AutoSkip/Assets/1920x1080`
  - `BetterGenshinImpact/GameTask/QuickTeleport/Assets/1920x1080`
- Import helper: `tools/import_bettergi_assets.py`

Imported AutoSkip assets:

- `disabled_ui.png`
- `hangout_skip.png`
- `page_close.png`

Imported reactive QuickTeleport assets:

- `quick_teleport/GoTeleport.png`
- `quick_teleport/MapScaleButton.png`
- `quick_teleport/MapSettingsButton.png`
- `quick_teleport/MapCloseButton.png`
- `quick_teleport/MapChoose.png`
- The ten candidate icon templates in `quick_teleport/`

These desktop BetterGI templates must be verified with `quick-teleport
--dry-run` on each Android or cloud-stream UI variant before live taps are
enabled. Their presence does not imply support for BetterGI's coordinate-driven
`TpTask`, map localization, path following, or Adventurers' Guild navigation.
