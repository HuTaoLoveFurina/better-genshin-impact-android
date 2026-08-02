from __future__ import annotations

import argparse
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bgia.cli import build_parser, main, merge_args
from bgia.config import Config


class ConfigAndCliTests(unittest.TestCase):
    def test_common_arguments_work_before_and_after_subcommand(self):
        before = build_parser().parse_args(["-c", "a.yaml", "run"])
        after = build_parser().parse_args(["run", "-c", "a.yaml"])
        self.assertEqual(before.config, "a.yaml")
        self.assertEqual(after.config, "a.yaml")

    def test_new_commands_parse(self):
        quick = build_parser().parse_args(["quick-teleport", "--dry-run", "--candidate-name", "A"])
        interact = build_parser().parse_args(["interact", "--name", "Katheryne", "-L", "en"])
        guild = build_parser().parse_args(["guild-assist", "--action", "daily"])
        self.assertTrue(quick.dry_run)
        self.assertTrue(interact.dry_run)
        self.assertTrue(guild.dry_run)
        self.assertEqual(interact.name, ["Katheryne"])
        self.assertEqual(guild.action, "daily")

    def test_cli_overrides_environment(self):
        args = build_parser().parse_args(["run", "-m", "last"])
        with patch.dict(os.environ, {"BGIA_OPTION_MODE": "second"}, clear=False):
            cfg = merge_args(Config(), args)
        self.assertEqual(cfg.option_mode, "last")

    def test_language_override_refreshes_default_keywords(self):
        args = build_parser().parse_args(["run", "-L", "en"])
        cfg = merge_args(Config(), args)
        self.assertEqual(cfg.lang, "en")
        self.assertIn("confirm", cfg.select_keywords)

    def test_explicit_yaml_keywords_survive_language_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("lang: zh-CN\nselect_keywords: [KeepMe]\n", encoding="utf-8")
            cfg = Config.load(path)
        cfg.apply_language("en")
        self.assertEqual(cfg.select_keywords, ["KeepMe"])

    def test_invalid_yaml_option_mode_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("option_mode: invalid\n", encoding="utf-8")
            cfg = Config.load(path)
        self.assertEqual(cfg.option_mode, "first")

    def test_invalid_yaml_language_keeps_the_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("lang: xx\n", encoding="utf-8")
            cfg = Config.load(path)
        self.assertEqual(cfg.lang, "zh-CN")

    def test_invalid_grace_value_is_reported_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("talk_grace_seconds: null\n", encoding="utf-8")
            with self.assertLogs("bgia", level="ERROR") as logs:
                exit_code = main(["-c", str(path), "devices"])
        self.assertEqual(exit_code, 1)
        self.assertIn("talk_grace_seconds", "\n".join(logs.output))

    def test_live_ui_taps_require_explicit_flags(self):
        quick = build_parser().parse_args(["quick-teleport", "--allow-unverified-ui"])
        interact = build_parser().parse_args(
            ["interact", "--name", "Katheryne", "--allow-unverified-tap"]
        )
        guild = build_parser().parse_args(
            ["guild-assist", "--action", "daily", "--allow-unverified-tap"]
        )
        self.assertFalse(quick.dry_run)
        self.assertFalse(interact.dry_run)
        self.assertFalse(guild.dry_run)


if __name__ == "__main__":
    unittest.main()
