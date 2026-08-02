# bgia — BetterGI-Inspired Visual Automation for Android

> A conservative Android port of selected visual-automation layers from [BetterGI](https://github.com/babalae/better-genshin-impact), released under the **GPL-3.0** open-source license.

Language / 語言：
[简体中文](./README/readme_sc.md) · [English](./README.md) · [繁體中文](./README/readme_tc.md) · [日本語](./README/readme_ja.md) · [한국어](./README/readme_ko.md) · [Русский](./README/readme_ru.md)

Telegram group: [@bettergi_for_android](https://t.me/bettergi_for_android)

The project currently provides auto story advancement, bounded right-side text observation, an
already-nearby Katheryne assistant, and reactive QuickTeleport confirmation. It is based on
**ADB vision capture + simulated taps** and does not read game memory. Desktop-derived interaction
and map assets are recognition-only by default on Android and cloud-stream clients.

Normal ADB mode needs no root, injection, or game-memory access. Root is required only for the
optional on-device local-shell mode. Both modes use "screenshot → recognize → `input tap`".

Supported: Genshin Impact **official / Bilibili / international servers**, as well as **cloud Genshin** (China and international).

## How It Works

```
adb screencap  ──►  16:9 render-region crop  ──►  template match + OCR  ──►  decide  ──►  adb input tap
```

Story automation uses a BetterGI-compatible Talk detector with Android-specific fallbacks and
enhancements:

| # | Scene | Behavior |
|---|---|---|
| 1 | Hangout screen | Tap the "Skip" button |
| 2 | Talk-state detection | Prefer `disabled_ui.png`; retain `stop_auto.png` and playing-text OCR as compatibility fallbacks |
| 3 | Active Talk options | Exclamation mark first; otherwise OCR-read a standard or explicit Android-special option layout |
| 4 | Active Talk advance | Tap a safe zone only when no option handled or paused the frame |
| 5 | Post-Talk grace | For 10 seconds, try bounded pop-up and tap-to-continue handlers |
| 6 | Inactive black screen | Tap at most once per second after grace handlers decline and the configured near-black threshold matches |

Normal OCR/pixel option handling is Talk-gated. An Android-specific gear/case layout may enter the
option path outside Talk only when its dedicated template matches; generic dark bands cannot.

Option decision is a five-level priority chain:
**custom priority words → sensitive words (pause) → built-in priority words → optional orange-key preference → fallback strategy (first/second/last/random)**.
Only an explicit custom-priority entry can override a pause keyword.

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

## Template Assets

The repository includes the BetterGI GPL-3.0 templates used by the current Talk detector,
hangout/popup handling, and reactive QuickTeleport. Their exact provenance is recorded in
[`assets/UPSTREAM.md`](./assets/UPSTREAM.md). Existing Android-specific option assets remain in
the same 1920×1080 baseline directory.

Desktop BetterGI templates can differ from native Android or cloud-stream UI rendering. Run
`check`; `quick-teleport`, `interact`, and `guild-assist` are recognition-only by default. Live
experiments require an explicit `--allow-unverified-*` flag. Replace a template with a crop from
your own device when needed.

Enter any dialogue scene in-game, then:

```bash
# Grab a frame
.venv/bin/python tools/grab_template.py shot        # produces shot.png

# Interactively select a region and save (needs GUI + opencv-python, not headless)
.venv/bin/python tools/grab_template.py pick --name icon_option.png

# Or measure pixel rect with an image viewer then crop directly (no GUI, recommended)
.venv/bin/python tools/grab_template.py crop --rect 1150,470,36,36 --name icon_option.png
```

The tool normalizes crops to the **1920×1080 baseline** before saving into
`assets/1920x1080/`. Runtime scaling handles resolution changes, but a different UI profile,
rendering style, or game update can still require a new template.

Story templates:

| File | Content | Impact if missing |
|---|---|---|
| `icon_option.png` | Bubble icon on the left of dialogue options | Loses bubble-anchored OCR; Talk-gated pixel fallback may still work |
| `icon_exclamation.png` | Exclamation icon for key quest options | Loses exclamation priority |
| `disabled_ui.png` | Top-left disabled UI marker | Primary Talk-state evidence |
| `stop_auto.png` | Top-left "Auto Play" button | Legacy Android/cloud fallback |
| `hangout_skip.png` | Skip button on hangout screens | Hangouts not auto-skipped |
| `page_close.png` | Top-right close button for pop-ups | Pop-ups not auto-closed |
| `icon_click_continue.png` | Bottom "tap-anywhere-to-continue" triangle/arrow | Degrades to pure-pixel shape detection (see "Screenshot-Only Mode" below) |

The 15 active reactive-map assets live under `assets/1920x1080/quick_teleport/`. The import
helper is:

```bash
.venv/bin/python tools/import_bettergi_assets.py /path/to/better-genshin-impact
```

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

# Observe stable exact text in the right-side ROI (recognition-only by default)
.venv/bin/python -m bgia.cli interact --name Katheryne -L en
# Experimental: no native-Android interaction-button anchor is packaged yet
.venv/bin/python -m bgia.cli interact --name Katheryne -L en --allow-unverified-tap

# Reactive QuickTeleport: the map and target/candidate list must already be visible
.venv/bin/python -m bgia.cli quick-teleport --candidate-name "Teleport Waypoint"
.venv/bin/python -m bgia.cli quick-teleport --candidate-type TeleportWaypoint --candidate-index 2
# Experimental live map taps with desktop-derived templates
.venv/bin/python -m bgia.cli quick-teleport --candidate-name "Teleport Waypoint" --allow-unverified-ui

# Guild observation: stand near Katheryne first; recognition-only by default
.venv/bin/python -m bgia.cli guild-assist --action daily
# Experimental prompt/option taps; option selection and rewards are not completion-verified
.venv/bin/python -m bgia.cli guild-assist --action expedition --allow-unverified-tap
```

`Ctrl+C` to stop.

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit. Key items:

```yaml
option_mode: first          # option strategy first/second/last/random/none
before_choose_delay: 0.0    # set 2~3s if you want to hear the voice lines
custom_priority:            # custom priority options
  - "继续深入"
pause_keywords:             # pause on hit to avoid mis-clicking consumable options
  - 退出秘境
  - 购买
interval: 0.6               # cloud Genshin streaming: suggest 0.8~1.0
talk_grace_seconds: 10.0    # safe post-dialogue window
legacy_talk_detection: true # retain stop_auto/playing-text fallbacks
```

Configuration priority is `defaults < YAML < environment variables < CLI`. Common options work
both before and after the subcommand.

## Capability Boundaries

`quick-teleport` is intentionally reactive. It can confirm an already-selected teleport button
or observe/choose an OCR-valid item from an already-visible overlapping-waypoint list. Recognition
is the default; live taps require `--allow-unverified-ui`. Duplicate matches are rejected unless
`--candidate-index` disambiguates them. A `map_closed` result means only that the big-map UI was
absent for two consecutive frames after the tap; landing is not verified. It does not:

- locate a waypoint by world coordinates;
- pan or zoom the map toward a named destination;
- implement BetterGI's coordinate-driven `TpTask`;
- switch map scenes or underground layers.

`interact` observes an exact normalized OCR target with confidence `>= 0.75` across two stable
frames. It has no native-Android interaction-button anchor or Main-HUD gate yet, so default mode
never taps. `--allow-unverified-tap` is an explicit experimental override.

`guild-assist` also has a strict boundary: the player must already be standing near Katheryne.
Default mode confirms only the stable localized name. Experimental mode taps the unverified OCR
box, requires an active Talk marker and a standard option-bubble anchor, and sends one requested
orange-option tap. It does not prove the option was accepted, navigate to the guild, claim reward
pages, or re-dispatch expeditions. Built-in guild terms cover `zh-CN`, `zh-TW`, `en`, and `fr`;
other game languages require both `--katheryne-name` and `--option-text`. Full automation requires map
localization, minimap positioning, camera/character orientation, virtual-joystick path following,
and dedicated reward-page assets that are not yet part of this repository.

### Trigger, Anchor, and Name-Reading Reference

All coordinates below are relative to the cropped 16:9 game render and scale from a 1920×1080
baseline (`s = render_width / 1920`).

| Layer | Trigger / anchor range | Text-reading and safety rule |
|---|---|---|
| Talk | `disabled_ui.png` in `x=0..W/3`, `y=0..H/8`; optional legacy checks use the left `W/5 × H/8` | Active Talk gates normal option handling and quick advance; loss of Talk starts the configured grace window |
| Standard dialogue options | Bubble/exclamation templates in `x=W/2`, `y=H/12`, `w=W/3`, `h=H-H/12-10`; OCR starts `8s` right of the lowest bubble and is `535s` wide | Short CJK options are retained; pause keywords win over built-in click keywords |
| Right-side text observer | `x=52%..95%`, `y=25%..80%` | NFKC + casefold + separator removal, exact match, score `>=0.75`, one unambiguous result, two stable frames; no tap by default |
| Reactive QuickTeleport list | Candidate icons at baseline `x=1270..1320`, `y=100..H-100`; OCR mask extends up to `200s` to the right | Near-white HLS text OCR; `--candidate-name` is an exact normalized match; duplicate rows require type/index disambiguation; button and row each require two stable frames |
| Guild option | Active Talk plus standard option-bubble anchor; option text uses the same bubble-relative `8s` / `535s` layout | Localized substring match, OCR score `>=0.75`, two stable orange frames; experimental mode reports only that a tap was sent |

For the source-level comparison with BetterGI's trigger dispatcher, upstream Katheryne/F-key
anchor, arrival tolerances, and full `TpTask` boundary, see
[`docs/BETTERGI_TRIGGER_REFERENCE.md`](./docs/BETTERGI_TRIGGER_REFERENCE.md).

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

**Cross-resolution / DPI / scale adaptation:** the script scales geometry automatically, subject
to UI-profile and template differences:
- **Resolution:** all templates/ROIs scale at runtime by "render width ÷ 1920"; 1920×1080
  baseline templates are geometrically scaled for 720p/1080p/2K. The render region is resolved
  on the first usable frame and re-resolved if an empty crop is detected.
- **DPI / scale (`wm density`, `wm size` Override):** `screencap` returns real display
  resolution (physical pixels) while `input tap` uses `wm size` logical pixels. When they
  differ due to DPI scaling, the script caches the "screenshot size ÷ display size" ratio and
  converts tap coordinates automatically, eliminating systematic offset.
- Switching resolution normally needs no coordinate edit. Switching UI profile, render style, or
  game version can still require dry-run verification and template recapture.

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

**OCR unavailable** — Run `.venv/bin/pip install rapidocr onnxruntime`. RapidOCR 3.x is pinned to
the PP-OCRv4 mobile recognition family so the mapped Chinese, Japanese, Korean, Latin, and Cyrillic
models resolve consistently. Thai remains degraded. Without OCR, story options can degrade to
position-based taps, while named interaction/map/guild recognition cannot run.

**Screenshot-Only fallback** — During an active Talk state, the script can use bounded
pure-pixel analysis when standard option OCR is unavailable:
- **Option detection:** scans the screen for "rounded dark bars darker than surroundings"
  (the common visual trait of all Genshin option UIs) and auto-taps the topmost one to advance
  item by item. Works for normal bubbles, gear-icon options, case-record lists, etc.
- **Tap-anywhere-to-continue:** detects the bottom-center triangle/arrow shape (pure shape
  detection, no template needed).
- Pure-pixel option clicks are Talk-gated. They are a fallback, not a guarantee across every UI
  theme, compression level, or game version.

**pip `externally-managed-environment`** — PEP 668 on Kali/Debian 12+; use the virtualenv from
the Installation section. Note `python3-xyz` in the error is just a placeholder name, not a real
package.

**`rapidocr-onnxruntime` won't install** — That old package requires Python `<3.13`. On
Python 3.13+ use `rapidocr>=2.0` (already in requirements.txt); the code is compatible with both
generations. The first use of a recognition family may download its ONNX model.

## Development

Run the automated suite with:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q bgia tools run.py
```

Repository language and contribution rules are documented in
[`CONTRIBUTING.md`](./CONTRIBUTING.md). Version history is maintained in
[`CHANGELOG.md`](./CHANGELOG.md).

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
