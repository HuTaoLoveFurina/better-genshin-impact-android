# Repository Instructions

## Language Policy

Use English for all implementation files, source comments, docstrings, developer documentation,
CHANGELOG entries, branch names, commit messages, pull-request titles and descriptions, issue
reports, review comments, release notes, and pull/push summaries.

The only content-language exceptions are:

- localized user-facing runtime strings, including launcher UI and tables such as `bgia/i18n.py`;
- user-supplied OCR keywords and examples that must match in-game text;
- translated end-user documents under `README/`.

Do not add bilingual source comments. Keep the English root `README.md` authoritative when a
translation has not yet been updated.

## Upstream Accuracy

This project is a GPL-3.0 port of selected BetterGI behavior. Preserve upstream attribution and
record imported asset revisions in `assets/UPSTREAM.md`.

Use capability names precisely:

- `quick-teleport` is reactive confirmation for a waypoint already visible in the map UI;
- it is not BetterGI's coordinate-driven `TpTask`;
- `guild-assist` requires the player to stand near Katheryne and is not automatic navigation or
  a complete reward/expedition task.

Never describe planned, unverified, or asset-dependent behavior as implemented.

## Verification

Run both commands before handing off a code change:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q bgia tools run.py
```

Keep interaction, guild, and map commands recognition-only by default. Experimental live behavior
must require an explicit `--allow-unverified-*` flag and must not be described as completion-verified.

## Changelog

Follow Keep a Changelog 1.1.0 and Semantic Versioning 2.0.0. Every released version must include
an ISO-8601 timestamp with timezone, grouped change categories, AI/model/tool attribution, and
links to the corresponding commits. An uncommitted working-tree entry must say `pending commit`
instead of inventing a hash.
