# Changelog

<!--
  Writing rules

  - Follow Keep a Changelog 1.1.0 and Semantic Versioning 2.0.0.
  - Use only the relevant categories: Added, Changed, Deprecated, Removed, Fixed, Security.
  - Released-version timestamps use `YYYY-MM-DD HH:mm +zzzz` and the Git committer date.
  - Every released item links to its implementing commit.
  - Every version identifies the AI/model and tool used to produce the change.
  - An uncommitted working-tree version says `pending commit`; never invent a hash.

  Project attribution history

  - All repository source and documentation through commit 66a8c76 were written by
    Hy3 (CodeBuddy IDE extension), as confirmed by the project owner.
  - Version 0.2.0 implementation changes were written by
    ChatGPT 5.6-sol (Codex CLI).
-->

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Timestamps include the
UTC+8 offset and are precise to the minute.

---

## [0.2.0] - 2026-08-02 18:51 +0800

> Author: ChatGPT 5.6-sol (Codex CLI)
>
> Implementation: 2026-08-02 18:48 +0800 ([`2017b8b`][2017b8b])
>
> Mainline merge: 2026-08-02 18:51 +0800 ([`3637792`][3637792])

### Added

- Added `TalkStateDetector`, using BetterGI's current `disabled_ui.png` marker as primary Talk
  evidence, optional Android/cloud legacy fallbacks, explicit evidence reporting, and a monotonic
  configurable post-dialogue grace window ([`2017b8b`][2017b8b]).
- Added recognition-first reactive `quick-teleport` support for an already-open map and visible
  waypoint panel/list, with ten BetterGI candidate icon types, near-white HLS OCR, exact normalized
  optional name matching, type/index filtering, ambiguity rejection, stable-frame checks, bounded
  timeouts, and explicit result states ([`2017b8b`][2017b8b]).
- Added a bounded right-side text observer with exact normalized matching, OCR confidence gating,
  ambiguity rejection, and two-frame position stability. Live OCR-box tapping is explicitly marked
  experimental and disabled by default because a native-Android interaction anchor is not yet
  packaged ([`2017b8b`][2017b8b]).
- Added an already-nearby Katheryne assistant. Default mode observes a stable localized name;
  experimental mode additionally requires confirmed Talk, a standard option-bubble anchor, and two
  orange option frames before sending a tap. It does not claim navigation or completion verification
  ([`2017b8b`][2017b8b]).
- Imported 18 currently used GPL-3.0 AutoSkip and QuickTeleport assets from BetterGI revision
  `b0c8fca19577fce0b6bdd38ec9fe2cd81babeb20`, with a deterministic import helper and an English
  provenance manifest ([`2017b8b`][2017b8b]).
- Added an English source reference for upstream dialogue triggers, QuickTeleport and `TpTask`
  boundaries, Katheryne/F-key name reading, route endpoints, and navigation tolerances
  ([`2017b8b`][2017b8b]).
- Added an automated test suite covering Talk evidence and routing, option safety, configuration and CLI
  precedence, multilingual OCR model resolution, stable text observation, Guild Talk gating,
  QuickTeleport state/safety behavior, asset packaging, and resolution-scaled geometry
  ([`2017b8b`][2017b8b]).
- Added English repository and contribution rules for source, comments, issues, branches, commits,
  pull requests, reviews, releases, pull/push summaries, changelog attribution, and precise upstream
  capability claims ([`2017b8b`][2017b8b]).

### Changed

- Gated standard option OCR, pure-pixel option clicks, and quick story advancement behind Talk
  evidence. The standard BetterGI option ROI is now separate from Android-specific extended layouts,
  and bubble-anchored OCR uses the upstream `8 × scale` offset and `535 × scale` width
  ([`2017b8b`][2017b8b]).
- Made pause keywords take precedence over built-in click keywords; custom priority remains the only
  intentional override. Reclassified abandon/reject phrases as pause terms in every localized table
  ([`2017b8b`][2017b8b]).
- Made all new interaction, Guild, and map commands recognition-only by default. Experimental input
  now requires `--allow-unverified-tap` or `--allow-unverified-ui` ([`2017b8b`][2017b8b]).
- Pinned RapidOCR 3.x recognition to PP-OCRv4 mobile with explicit language, OCR-version, and
  model-type parameters so the mapped Chinese, Japanese, Korean, Latin, and Cyrillic families resolve
  consistently; initialization errors now retain provider-specific causes ([`2017b8b`][2017b8b]).
- Added bounded finite-value validation for task timeouts, loop delays, Talk grace, black/orange
  ratios, story template confidence, and the independent QuickTeleport threshold
  ([`2017b8b`][2017b8b]).
- Updated the English README with truthful trigger/ROI/name-reading rules, default-safe command
  examples, verified Guild localization limits, and the distinction between reactive QuickTeleport,
  coordinate-driven `TpTask`, and full Guild navigation ([`2017b8b`][2017b8b]).
- Updated the package version from `0.1.0` to `0.2.0` ([`2017b8b`][2017b8b]).

### Fixed

- Fixed normal dialogue being missed whenever auto-play was disabled by using BetterGI's current
  Talk marker instead of relying only on the legacy auto-play button or OCR ([`2017b8b`][2017b8b]).
- Fixed pause keywords and `option_mode: none` allowing the same frame to continue into a quick
  story tap; both now stop frame routing without input ([`2017b8b`][2017b8b]).
- Fixed one- and two-character CJK options being discarded as noise, `orange_ratio` being ignored,
  and continue-indicator area thresholds remaining unscaled at lower resolutions
  ([`2017b8b`][2017b8b]).
- Fixed case-sensitive continue OCR and normalized positional handling across `first`, `second`,
  `last`, and `random` fallback paths ([`2017b8b`][2017b8b]).
- Fixed invalid YAML languages overwriting their documented fallback, malformed grace values escaping
  the CLI error handler, and environment overrides incorrectly taking priority over CLI arguments
  ([`2017b8b`][2017b8b]).
- Fixed README-style common arguments so they work before or after subcommands, and expanded the
  environment check to report story, optional, reactive-map, and mapped OCR readiness separately
  ([`2017b8b`][2017b8b]).

### Security

- Prevented broad one-frame OCR matches, low-confidence text, duplicate map names, non-finite
  timeouts, unsafe map thresholds, and post-deadline recognition from silently entering new live-tap
  paths. BetterGI desktop templates remain explicitly unverified for native Android/cloud rendering
  ([`2017b8b`][2017b8b]).

---

## [0.1.0] - 2026-08-02 17:01 +0800

> Author: Hy3 (CodeBuddy IDE extension)
>
> Final integration: 2026-08-02 17:01 +0800 ([`66a8c76`][66a8c76])

### Added

- Created the ADB screenshot-and-tap Android story skipper with 16:9 render-region detection,
  cross-device coordinate scaling, DPI override compensation, OCR option selection, pure-pixel
  fallbacks, local rooted-Android mode, and Linux/Windows launchers
  ([`6a768b6`][6a768b6] · [`a108f82`][a108f82]).
- Added GPL-3.0 licensing and explicit BetterGI upstream attribution ([`f62bee2`][f62bee2]).
- Added multilingual end-user READMEs, language navigation, BetterGI acknowledgements, and project
  Star History links ([`a899cf7`][a899cf7] · [`21b2169`][21b2169]).
- Added game-language configuration, OCR language mapping, and RapidOCR-based multilingual
  recognition infrastructure ([`1cc5464`][1cc5464]).

### Changed

- Replaced the original 1920×1080 auto-play template with an updated capture
  ([`a4adc24`][a4adc24]).
- Translated and clarified core source comments in English and made launcher menus bilingual
  ([`b8ca2d0`][b8ca2d0] · [`2e4f866`][2e4f866] · [`66a8c76`][66a8c76]).

### Fixed

- Fixed solid-looking dialogue option bands being rejected by the pure-pixel fallback
  ([`8a7e576`][8a7e576]).
- Excluded local environment values, device identifiers, logs, and PID files from Git
  ([`1733092`][1733092]).

<!-- Commit links -->
[3637792]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/3637792f9dbc0c91ccecd973d1b534f7d8fbf857
[2017b8b]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/2017b8bbb4816b51cea0773a2a10af01d1657232
[6a768b6]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/6a768b66336a7523a0bd5f96da2b90746d256a30
[a108f82]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/a108f825d1fdaa3a51baef7649644173807bb57e
[f62bee2]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/f62bee235568d8a744e3f818a9730beca63b16dd
[1733092]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/1733092307c30264561fdee3163d3acc717fd8ab
[8a7e576]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/8a7e5769448e34e696d9659c63ed4e075ac48193
[a899cf7]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/a899cf7ca49fe5a669561fb26cc89f51575240e3
[21b2169]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/21b2169379a9c14c05bc075767e784af0360a9ef
[a4adc24]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/a4adc24184a85b1d5a75a0474fdd76ea80dad6b0
[1cc5464]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/1cc5464b3d761aaaa2ad967ba5c7d6d7499053bf
[b8ca2d0]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/b8ca2d0e29e365a57c995dd05eba4c0ce949bbec
[2e4f866]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/2e4f8662c219fff95e7e66a6e33c84011d75bace
[66a8c76]: https://github.com/HuTaoLoveFurina/better-genshin-impact-android/commit/66a8c7661d7bbf1a13c309878248bb16c6682c9e
