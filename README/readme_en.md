# bgia — Genshin Impact Auto Story Skipper for Android

> A port of the `AutoSkip` module from [BetterGI](https://github.com/babalae/better-genshin-impact), released under the **GPL-3.0** open-source license.

Language / 語言：
[简体中文](./README.md) · [English](./README/readme_en.md) · [繁體中文](./README/readme_tc.md) · [日本語](./README/readme_ja.md) · [한국어](./README/readme_ko.md) · [Русский](./README/readme_ru.md)

Telegram group: [@bettergi_for_android](https://t.me/bettergi_for_android)

An auto story-skipping script for Genshin Impact based on **ADB vision capture + simulated taps**, with logic ported from the `AutoSkip` module of [BetterGI](https://github.com/babalae/better-genshin-impact).

No root, no injection, no game-memory access — it only does "screenshot → recognize → `input tap`", equivalent to a human tapping the screen.

Supported: Genshin Impact **official / Bilibili / international servers**, as well as **cloud Genshin** (China and international).

## How It Works

```
adb screencap  ──►  16:9 render-region crop  ──►  template match + OCR  ──►  decide  ──►  adb input tap
```

Each frame is processed by the following priority (consistent with BetterGI):

| # | Scene | Behavior |
|---|---|---|
| 1 | Hangout screen | Tap the "Skip" button |
| 2 | Dialogue options | Exclamation mark first; otherwise OCR-read the option text and decide by rules |
| 3 | Playing | Tap the safe zone to fast-forward dialogue |
| 4 | Black-screen cutscene | Tap once per second to advance |
| 5 | Pop-up page | Tap the top-right close button |
| 6 | Tap-anywhere-to-continue | Auto-tap to advance when a "tap anywhere to continue" prompt appears (e.g. Fontaine main story, see `click_continue`) |

Option decision is a five-level priority chain:
**custom priority words → built-in priority words → sensitive words (pause) → orange key options → fallback strategy (first/last/random)**

## Installation

```bash
# 1. Install Android Platform Tools (provides adb)
sudo apt install android-tools-adb        # Debian/Ubuntu/Kali
# macOS: brew install android-platform-tools

# 2. Create a virtual environment and install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> **Kali / Debian 12+ users**: these systems enable PEP 668 protection; a direct `pip install`
> raises `externally-managed-environment`. **You must use the virtualenv approach above**;
> do not add `--break-system-packages` (it pollutes system Python and may break apt).
> If venv is missing, first run `sudo apt install python3-full python3-venv`.

After that, run all commands with `.venv/bin/python`; or `source .venv/bin/activate` first
(then `python` works directly), and `deactivate` to exit.

## Cross-Platform

This project supports **Linux / macOS / Windows**, and **rooted Android devices running locally** (no PC needed).

### Windows

1. Install Python 3.10+ (check "Add to PATH").
2. Download [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools),
   add the directory containing `adb.exe` to the system `PATH`; or place `adb.exe` in the
   project root / `platform-tools/` (the script auto-discovers it).
3. Use `bgia.bat` (same menu as `bgia.sh`):
   ```bat
   bgia.bat
   ```
   Or directly from the command line:
   ```bat
   .venv\Scripts\python.exe -m bgia.cli run
   ```

### Rooted Android device (local shell mode)

Run directly in **Termux (rooted) / Magisk terminal** on the phone; screenshots and taps go
through `/system/bin/screencap` and `/system/bin/input` — **no PC, no adb forwarding**.

1. Install Python and dependencies in Termux (Termux ships `clang`/`libc++`):
   ```bash
   pkg update && pkg install python clang libc++ make
   python -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
2. Launch with root (otherwise `screencap` / `input` cannot access the screen):
   ```bash
   su
   cd /data/data/com.termux/files/home/bgia   # your project path
   .venv/bin/python -m bgia.cli run --local
   ```
3. Environment variables work the same: `BGIA_OPTION_MODE=second .venv/bin/python -m bgia.cli run --local`

> Local mode skips adb connection and calls system `screencap -p` / `input tap` directly.
> If screenshots fail, confirm you ran `su` and `/system/bin/screencap` exists.

## Connect Your Phone

**USB:** Enable "Developer options → USB debugging", plug in, and tap "Allow" on the phone.

**Wireless (Android 11+):** Enable "Developer options → Wireless debugging" and pair with the code:

```bash
adb pair 192.168.1.20:37xxx      # enter the pairing code shown on the phone
adb connect 192.168.1.20:5555
```

**Wireless (Android 10 and below):** first run `adb tcpip 5555` over USB once, then `adb connect <IP>:5555`.

Verify the connection:

```bash
python -m bgia.cli devices
```

## Prepare Template Assets

The script relies on a few UI template images. Because the original templates are not
distributed with this repo, capture them once from **your own device screenshots** (this also
adapts to UI differences across servers).

Enter any dialogue scene in-game, then:

```bash
# Grab a frame
.venv/bin/python tools/grab_template.py shot        # produces shot.png

# Interactively select a region and save (needs GUI + opencv-python, not headless)
.venv/bin/python tools/grab_template.py pick --name icon_option.png

# Or measure pixel rect with an image viewer then crop directly (no GUI, recommended)
.venv/bin/python tools/grab_template.py crop --rect 1150,470,36,36 --name icon_option.png
```

The tool auto-normalizes crops to the **1920×1080 baseline** before saving into
`assets/1920x1080/`, so switching phones or resolutions needs no re-capture.

Required templates (missing ones auto-degrade gracefully, no crash):

| File | Content | Impact if missing |
|---|---|---|
| `icon_option.png` | Bubble icon on the left of dialogue options | Cannot locate options; degrades to play-advance |
| `icon_exclamation.png` | Exclamation icon for key quest options | Loses exclamation priority |
| `stop_auto.png` | Top-left "Auto Play" button | Falls back to OCR for play-state |
| `hangout_skip.png` | Skip button on hangout screens | Hangouts not auto-skipped |
| `page_close.png` | Top-right close button for pop-ups | Pop-ups not auto-closed |
| `icon_click_continue.png` | Bottom "tap-anywhere-to-continue" triangle/arrow | Degrades to pure-pixel shape detection (see "Screenshot-Only Mode" below) |

## Usage

```bash
# Self-check: resolution, package, render region, templates, OCR
.venv/bin/python -m bgia.cli check

# Run
.venv/bin/python -m bgia.cli run

# Common combos
.venv/bin/python -m bgia.cli run -c config.yaml          # use config file
.venv/bin/python -m bgia.cli run -w 192.168.1.20:5555    # wireless connect + run
.venv/bin/python -m bgia.cli run -m last                 # prefer last option
.venv/bin/python -m bgia.cli run --debug -v              # debug screenshots + verbose log
```

`Ctrl+C` to stop.

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit. Key items:

```yaml
option_mode: first          # option strategy first/last/random/none
before_choose_delay: 0.0    # set 2~3s if you want to hear the voice lines
custom_priority:            # custom priority options
  - "继续深入"
pause_keywords:             # pause on hit to avoid mis-clicking consumable options
  - 退出秘境
  - 购买
interval: 0.6               # cloud Genshin streaming: suggest 0.8~1.0
```

## Server Notes

| Server | Package |
|---|---|
| Official | `com.miHoYo.Yuanshen` |
| Bilibili | `com.miHoYo.ys.bilibili` |
| International | `com.miHoYo.GenshinImpact` |
| Cloud (China) | `com.miHoYo.cloudgames.ys` |
| Cloud (Intl) | `com.miHoYo.cloudgames.genshinimpact` |

Package auto-detected, or force with `-p`.

**Cloud Genshin note:** the picture is video streaming with encode blur and network latency.
Raise `interval` to `0.8~1.0` and lower `template_threshold` to `0.72~0.75`. Streaming
letterbox is auto-cropped.

**Notch/Full-screen adaptation:** On 20:9 etc. non-16:9 screens the game is centered with side
safe areas; the script auto-locates the true 16:9 render region and maps all coordinates to it,
no manual config needed.

**Cross-resolution / DPI / scale adaptation:** the script auto-adapts to any phone quirks,
no manual config:
- **Resolution:** all templates/ROIs scale at runtime by "render width ÷ 1920"; 1920×1080
  baseline templates work for 720p/1080p/2K; the render region is auto-detected per frame
  (black-edge trim + 16:9 convergence), not hardcoded.
- **DPI / scale (`wm density`, `wm size` Override):** `screencap` returns real display
  resolution (physical pixels) while `input tap` uses `wm size` logical pixels. When they
  differ due to DPI scaling, the script caches the "screenshot size ÷ display size" ratio and
  converts tap coordinates automatically, eliminating systematic offset.
- Thus switching phones, changing display scale, or switching in-game resolution needs no
  template re-capture or config change.

## FAQ

**Options not recognized** — Run `check` to confirm templates are ready; lower
`template_threshold` to `0.72`; if still failing, export screenshots under `debug/` with
`--debug` and verify templates match your device UI (different servers differ slightly;
re-capture).

**Tap position offset** — Render-region detection is wrong; run `check` and verify the
render-region numbers match the actual screen; ensure the game is landscape and in foreground.
If you changed system display scale (`wm size` / `wm density`), the script auto-converts by
physical/logical ratio; if still off, run `adb shell wm size reset` and `adb shell wm density
reset` to restore scale.

**Screenshots are slow** — Some devices have slow `screencap`; the script already prefers the
raw pixel pipeline (faster than PNG). Raise `interval` a bit.

**OCR unavailable** — Run `.venv/bin/pip install rapidocr onnxruntime`. The script still runs
without it; options degrade to position-based taps.

**Screenshot-Only Mode (pure-pixel fallback)** — Even with templates uncollected or OCR
uninstalled, the script recognizes options and advance prompts via pure-pixel analysis:
- **Option detection:** scans the screen for "rounded dark bars darker than surroundings"
  (the common visual trait of all Genshin option UIs) and auto-taps the topmost one to advance
  item by item. Works for normal bubbles, gear-icon options, case-record lists, etc.
- **Tap-anywhere-to-continue:** detects the bottom-center triangle/arrow shape (pure shape
  detection, no template needed).
- This is the final fallback when templates/OCR are missing, guaranteeing no deadlock in any
  environment.

**pip `externally-managed-environment`** — PEP 668 on Kali/Debian 12+; use the virtualenv from
the Installation section. Note `python3-xyz` in the error is just a placeholder name, not a real
package.

**`rapidocr-onnxruntime` won't install** — That old package requires Python `<3.13`. On
Python 3.13+ use `rapidocr>=2.0` (already in requirements.txt); the code is compatible with both
generations. The first run auto-downloads ~20MB of ONNX models.

## Disclaimer

This project is for technical learning and communication only. The script operates via ADB
simulated taps; it does not modify game files, read/write game memory, or interfere with network
communication. Users bear all consequences of using automation tools, including but not limited
to account risk. Please comply with the relevant game's Terms of Service.

## Acknowledgements

Everything in this project stands on the shoulders of
[**BetterGI · Better Genshin Impact**](https://github.com/babalae/better-genshin-impact).

- Thanks to [babalae](https://github.com/babalae) and every developer and contributor of BetterGI.
  The entire design behind the `AutoSkip` module — automatic story advancement, option
  recognition, playback-state detection — is the direct blueprint for this Android port. Without
  their years of engineering practice and their willingness to share it openly, this project
  would not exist.
- Thanks to everyone in the BetterGI community who filed issues, contributed template assets, and
  reported edge cases. Those hard-won details saved this port from countless detours.
- Thanks to BetterGI for staying open source under **GPL-3.0**. That openness is what allowed the
  knowledge to travel to a new platform. This project is released under GPL-3.0 as well, passing
  that openness forward.

A tribute to every line of code and every developer of the original project.

## Star History

<a href="https://www.star-history.com/?repos=HuTaoLoveFurina%2Fbetter-genshin-impact-android&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=HuTaoLoveFurina/better-genshin-impact-android&type=date&theme=dark&legend=top-left&sealed_token=PsfqI2ssPFXeokK1J0nVWKxzFeC7L0jkn1aBG6wKASZieIrXpIAYYjlx6Jlg-ISBs6Y5l5fy42HWD1q-pchInjMblwOz12D6fbw6q9dL06YWsUZYOOFxt_-leWNY1l8rPheUnBUOIyfqvxPHfbUIG1T_QzNd8vj1g1IktGO4DdjeJ1F0u_9XW2tm7383" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=HuTaoLoveFurina/better-genshin-impact-android&type=date&legend=top-left&sealed_token=PsfqI2ssPFXeokK1J0nVWKxzFeC7L0jkn1aBG6wKASZieIrXpIAYYjlx6Jlg-ISBs6Y5l5fy42HWD1q-pchInjMblwOz12D6fbw6q9dL06YWsUZYOOFxt_-leWNY1l8rPheUnBUOIyfqvxPHfbUIG1T_QzNd8vj1g1IktGO4DdjeJ1F0u_9XW2tm7383" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=HuTaoLoveFurina/better-genshin-impact-android&type=date&legend=top-left&sealed_token=PsfqI2ssPFXeokK1J0nVWKxzFeC7L0jkn1aBG6wKASZieIrXpIAYYjlx6Jlg-ISBs6Y5l5fy42HWD1q-pchInjMblwOz12D6fbw6q9dL06YWsUZYOOFxt_-leWNY1l8rPheUnBUOIyfqvxPHfbUIG1T_QzNd8vj1g1IktGO4DdjeJ1F0u_9XW2tm7383" />
 </picture>
</a>
