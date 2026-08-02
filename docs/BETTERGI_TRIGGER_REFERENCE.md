# BetterGI Trigger, Anchor, and Name-Reading Reference

This document records the source-level behavior used to design the Android port. The upstream
baseline is BetterGI revision
[`b0c8fca19577fce0b6bdd38ec9fe2cd81babeb20`](https://github.com/babalae/better-genshin-impact/tree/b0c8fca19577fce0b6bdd38ec9fe2cd81babeb20).
Paths and line numbers below refer to that revision.

The terms `QuickTeleport` and `TpTask` are intentionally kept separate. QuickTeleport reacts to
an already-visible map UI. `TpTask` localizes and controls the map from world coordinates.

## 1. Story Dialogue and AutoSkip

### Dispatch and trigger conditions

The screenshot dispatcher normally captures every 50 ms. `AutoSkipTrigger` has priority `20`, is
non-exclusive, and declares support for the `Talk` UI category. It also throttles its own work to
once per 200 ms.

Relevant sources:

- `BetterGenshinImpact/GameTask/TaskTriggerDispatcher.cs:129-169,385-436`
- `BetterGenshinImpact/GameTask/AutoSkip/AutoSkipTrigger.cs:36-62,189-225`

Current upstream considers dialogue active when either the dispatcher classifies the frame as
`Talk` or `Bv.IsInTalkUi()` matches `disabled_ui.png`. The template ROI is:

```text
rect(0, 0, captureWidth / 3, captureHeight / 8)
1920×1080: (0, 0, 640, 135)
default template threshold: 0.8
```

Sources:

- `BetterGenshinImpact/GameTask/AutoSkip/AutoSkipTrigger.cs:202-205`
- `BetterGenshinImpact/GameTask/Common/BgiVision/BvStatus.cs:326-335`
- `BetterGenshinImpact/GameTask/AutoSkip/Assets/Recognition.json:13-17`

`StopAutoButton` and `PlayingText` remain defined in `Recognition.json`, but the current C# Talk
check does not call them. They are legacy definitions, not the primary current trigger.

### Per-capture order

After voice-wait handling and the 200 ms throttle, current upstream does the following:

1. Handles the short daily-reward escape window and foreground/background state.
2. For 10 seconds after Talk disappears, handles pop-ups; item submission is checked only during
   the first 3 seconds.
3. While Talk is active, sends Space or the configured interaction action to advance.
4. Still in the same Talk pass, checks ordinary dialogue options.
5. If no ordinary option was found, checks hangout options at most once per 1200 ms.
6. Outside Talk, checks the black-screen handler.

Source: `BetterGenshinImpact/GameTask/AutoSkip/AutoSkipTrigger.cs:189-312`.

The Android port deliberately recognizes options before sending a touch advance. Direct touch has
a greater risk of landing on a newly rendered option than upstream's keyboard-based Space action.

### Dialogue-option anchors and OCR

The standard option template ROI is:

```text
rect(captureWidth / 2,
     captureHeight / 12,
     captureWidth - captureWidth / 2 - captureWidth / 6,
     captureHeight - captureHeight / 12 - 10)

1920×1080: (960, 90, 640, 980)
```

Foreground mouse mode first checks the exclamation template and then all option-bubble templates.
The lowest bubble defines the OCR crop:

```text
x = lowestBubble.right + 8 * assetScale
y = captureHeight / 12
width = 535 * assetScale
height = lowestBubble.bottom + 30 * assetScale - captureHeight / 12
```

OCR results are sorted by Y. Empty results, short pure-ASCII alphanumeric debris, and selected
large Y gaps are filtered. Upstream uses substring matching for custom/select/pause keywords and
clicks the OCR region center. If bubbles exist but OCR returns nothing, it falls back to a bubble
position.

Sources:

- `BetterGenshinImpact/GameTask/AutoSkip/Assets/Recognition.json:3-5,35-57`
- `BetterGenshinImpact/GameTask/AutoSkip/AutoSkipTrigger.cs:579-809`

AutoSkip's orange test is a narrow RGB range (`243..255`, `195..205`, `48..55`) with ratio
`>0.06`; it is not the same HSV test used by the Guild task.

### What AutoSkip does not read

AutoSkip OCR reads option text. It does not OCR the current speaker or NPC name. Named interaction
reading belongs to the separate F/interact-key pipeline described below.

## 2. Reactive QuickTeleport

### Trigger flow

`QuickTeleportTrigger` has priority `21`, supports `BigMap`, is non-exclusive, and is disabled by
default. It runs at most once per 300 ms. Optional hotkey mode additionally requires the configured
key to be held.

When the frame is classified or recognized as the big map, upstream executes this order:

1. Click a visible Teleport button immediately.
2. Otherwise return if `MapCloseButton` is visible.
3. Otherwise return if `MapChoose` is visible.
4. Otherwise scan the already-visible overlapping-waypoint list.
5. Click the first/topmost OCR-valid row, wait the configured panel delay, capture once more, and
   check the Teleport button once.

Sources:

- `BetterGenshinImpact/GameTask/QuickTeleport/QuickTeleportTrigger.cs:18-105`
- `BetterGenshinImpact/GameTask/QuickTeleport/QuickTeleportConfig.cs:10-31`

### Screen anchors

All expressions use the asset scale `s`.

| Object | ROI expression | 1920×1080 |
|---|---|---|
| Teleport button | `rect(1440*s, H-120*s, 100*s, 120*s)` | `(1440,960,100,120)` |
| Map scale | `rect(30*s, 440*s, 40*s, 200*s)` | `(30,440,40,200)` |
| Map close | `rect(W-107*s, 19*s, 58*s, 58*s)` | `(1813,19,58,58)` |
| Map settings | `rect(25*s, 990*s, 58*s, 62*s)` | `(25,990,58,62)` |
| Map selector | `rect(W-480*s, 0, 100*s, 70*s)` | `(1440,0,100,70)` |
| Candidate icon column | `(1270*s,100*s,50*s,H-200*s)` | `(1270,100,50,880)` |

Sources:

- `BetterGenshinImpact/GameTask/QuickTeleport/Assets/Recognition.json:3-31`
- `BetterGenshinImpact/GameTask/QuickTeleport/Assets/QuickTeleportAssets.cs:17-37`

Ten candidate types are active: Teleport Waypoint, Statue of the Seven, two Domain variants,
Obsidian Totem Pole, Portable Waypoint, Mansion, Sub-Space Waypoint, Nod-Krai Meeting Point, and
Tablet of Tona. The active bulk matcher uses grayscale threshold `0.8`, or `0.7` for HDR capture.

### How upstream reads a waypoint name

For each icon, ordered top-to-bottom, upstream constructs this text crop:

```text
x = candidateColumn.x + icon.x + icon.width
y = candidateColumn.y + icon.y - 8
width = 200
height = icon.height + 16
```

The current `-8`, `200`, and `+16` constants are literal pixels in upstream and are not multiplied
by `s`. It converts BGR to HLS and keeps `(H=0..180, L=245..255, S=0..15)`, producing a near-white
text mask. Empty and one-character OCR results are rejected.

Crucially, upstream QuickTeleport does **not** match a requested name. The OCR result is only a
validity guard and log label; removing `>` affects only logging. The first/topmost OCR-valid row is
clicked.

Sources: `BetterGenshinImpact/GameTask/QuickTeleport/QuickTeleportTrigger.cs:131-173`.

The Android port is stricter: `--candidate-name` uses NFKC, case folding, separator removal, and an
exact match. Duplicate matches are rejected unless a type/index disambiguates them. This is a port
safety extension, not a claim about upstream behavior.

## 3. Full Coordinate-Driven `TpTask`

`TpTask` is a separate subsystem. It loads scene waypoint data from
`GameTask/AutoTrackPath/Assets/tp.json`, maps stored arrays as `X=Position[2]` and
`Y=Position[0]`, finds nearby database points, opens and localizes the map, switches layers,
adjusts zoom, drags toward a world coordinate, resolves nearby icons/candidate panels, and waits
for teleport completion.

Key sources:

- `BetterGenshinImpact/GameTask/Common/Element/Assets/MapLazyAssets.cs:20-45`
- `BetterGenshinImpact/GameTask/AutoTrackPath/Model/GiWorldPosition.cs:9-46`
- `BetterGenshinImpact/GameTask/AutoTrackPath/TpTask.cs:380-420,1066-1133,1197-1325,1975-2097,2343-2379`

The Android repository currently lacks `tp.json`, map feature assets/localization, zoom/drag
control, scene/layer switching, and completion fixtures. Reactive QuickTeleport must therefore not
be described as full `TpTask`.

## 4. Adventurers' Guild Task

### Entry and route triggers

`GoToAdventurersGuildTask` is invoked by OneDragon daily-reward flow, the scripting API, and the
path executor's periodic expedition-reward check. It loads a country-specific path JSON and sets
this authoritative early end action:

```text
Bv.FindFAndPress(frame, localizedKatheryneName)
```

Source: `BetterGenshinImpact/GameTask/Common/Job/GoToAdventurersGuildTask.cs:150-172`.

The revision contains six route files. Every current route point uses walking movement; a
`teleport` point type is not the same as `move_mode=teleport`.

| Country | Route start | Final target | Points |
|---|---:|---:|---:|
| Mondstadt | `(-867.6885, 2281.3660)` | `(-913.5100, 2232.6700)` | 4 |
| Liyue | `(267.9473, -665.1191)` | `(203.5127, -659.8633)` | 8 |
| Inazuma | `(-4402.5449, -3052.9766)` | `(-4418.5430, -3086.8789)` | 4 |
| Sumeru | `(2786.9990, -503.1045)` | `(2765.5186, -476.0566)` | 4 |
| Fontaine | `(4509.0020, 3630.5986)` | `(4495.9414, 3638.5205)` | 3 |
| Nod-Krai | `(9458.0342, 1660.6646)` | `(9461.4209, 1663.5850)` | 2 |

Ordinary path-point arrival uses navigation distance `<4`. The final precision approach uses
distance `<2`, at most 25 small steps, each pressing forward for 60 ms. The F/name end action runs
before each new position calculation, so the route can terminate as soon as the game exposes the
Katheryne prompt. These are navigation-coordinate tolerances, not a fixed NPC interaction radius.

Sources:

- `BetterGenshinImpact/GameTask/AutoPathing/PathExecutor.cs:783-804,1058-1099,1419-1424`
- `BetterGenshinImpact/GameTask/Common/Element/Assets/Json/冒险家协会_*.json`

### How upstream reads "Katheryne"

The configured interaction-key template is searched in:

```text
rect(1090*s, 330*s, 60*s, 420*s)
```

After the key icon matches, the OCR area is relative to that anchor:

```text
x = key.x + 115*s
y = key.y
width = (400-115)*s = 285*s
height = key.height
```

Paddle OCR then applies `Regex.IsMatch(result.Text, localizedKatheryneName)`. A match sends the
configured interaction key; upstream does not click arbitrary text. The current implementation
returns after examining the first OCR result, so a valid name in a later OCR box is not checked.

Sources:

- `BetterGenshinImpact/GameTask/AutoPick/Assets/Recognition.json:3-7`
- `BetterGenshinImpact/GameTask/AutoPick/AutoPickConfig.cs:17-30`
- `BetterGenshinImpact/GameTask/Common/BgiVision/BvSimpleOperation.cs:180-230`

Verified upstream resource strings are:

| Game language | NPC | Expedition keyword | Daily keyword |
|---|---|---|---|
| Simplified Chinese | `凯瑟琳` | `探索` | `每日` |
| Traditional Chinese | `凱瑟琳` | `探索` | `每日` |
| English | `Katheryne` | `Expedition` | `Daily` |
| French | `Catherine` | `Expédition` | `quotidien` |

### Guild dialogue-option trigger

The task waits for Talk, waits 500 ms, and retries option OCR. After the first text-bearing frame,
it waits another second and re-captures so the text can stabilize. It performs a localized
substring match and, when required, checks HSV orange `(10,150,150)..(25,255,255)` at ratio `>0.1`.

Its bubble-relative OCR crop starts at `lowest.right + 8*s`, has width `535*s`, uses `y=H/8`,
and calculates height using a `H/12` subtraction. That `H/8` versus `H/12` mismatch is present in
current upstream. The method also builds a filtered result list but returns the unfiltered OCR list.

Source: `BetterGenshinImpact/GameTask/Common/Job/ChooseTalkOptionTask.cs:43-95,152-224`.

## 5. Android Port Boundary

| Layer | Present now | Still required for full parity |
|---|---|---|
| Dialogue | Talk gating, option anchors/OCR, conservative touch ordering, grace handlers | Device-specific fixtures for every Android/cloud UI variant |
| QuickTeleport | Recognition-only default, visible-row OCR, exact optional name filter, ambiguity rejection, experimental taps | Map localization/control, database resolver, layer/scene control, landing verification |
| Guild | Stable bounded name observation; experimental Talk/bubble/orange-gated taps | Native interaction-key anchor, minimap navigation, joystick/camera control, reward and expedition completion verification |

The implementation and documentation must continue using these precise capability names until the
missing infrastructure is implemented and validated.
