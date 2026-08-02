# Contributing

Thank you for improving this Android port of BetterGI's visual-automation workflows.

## Project Language

English is the working language of this repository. Use English for:

- source files, inline comments, docstrings, and developer-facing configuration descriptions;
- issues, branch names, commits, pull requests, reviews, release notes, and pull/push summaries;
- the root README, CHANGELOG, contribution guides, and asset provenance records.

Localized user-facing runtime strings (including launcher UI), OCR fixtures that must match in-game
text, and translated files under `README/` may use their target language. Keep those translations
separate from source-code comments and development metadata.

## Scope and Upstream Attribution

The repository is licensed under GPL-3.0 and ports selected behavior from
[BetterGI](https://github.com/babalae/better-genshin-impact). Preserve source attribution for
copied logic and visual assets. Record the exact upstream revision in `assets/UPSTREAM.md`.

Do not use `teleport`, `TpTask`, `navigation`, or `guild automation` as interchangeable terms.
The current implementation provides:

- a Talk-state-driven story skipper;
- bounded right-side OCR observation, with no live tap by default;
- an already-nearby Katheryne observer with explicitly experimental prompt/option taps;
- reactive QuickTeleport observation for an already-visible map target, with live taps explicitly
  gated behind an unverified-UI flag.

Full coordinate-driven teleport and guild navigation require map localization and path-following
infrastructure and must not be claimed until they are implemented and tested.

## Tests

Create or update tests for every behavior change. Before opening a pull request, run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q bgia tools run.py
```

Map and interaction commands are recognition-only by default. Test them before using the explicit
`--allow-unverified-ui` or `--allow-unverified-tap` overrides. Include the UI
profile, resolution, game language, package, and whether the input was native Android or a cloud
stream in the pull-request description.

## Commit and Pull-Request Style

Use concise English Conventional Commit subjects where practical, for example:

```text
feat: add reactive quick teleport confirmation
fix: gate option clicks behind active dialogue state
docs: document BetterGI asset provenance
```

Pull requests should explain the user-visible outcome, safety boundaries, tests run, assets added
or changed, and any remaining platform limitations.

## Changelog

Update `CHANGELOG.md` for user-visible changes. Follow Keep a Changelog categories and Semantic
Versioning. Include the completion timestamp with timezone, author attribution in the form
`AI/model (tool)`, and commit links. Use `pending commit` for local changes that have not been
committed yet; never fabricate a commit hash.
