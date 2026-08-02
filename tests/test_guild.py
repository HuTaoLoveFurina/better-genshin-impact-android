from __future__ import annotations

import unittest
from unittest.mock import Mock

from bgia.config import Config
from bgia.guild import GuildAction, GuildAssistant
from bgia.interaction import LocatedText
from bgia.vision import Match


class GuildAssistantTests(unittest.TestCase):
    def make_assistant(self) -> GuildAssistant:
        assistant = GuildAssistant.__new__(GuildAssistant)
        assistant.device = Mock()
        assistant.config = Config(lang="en")
        assistant.interaction = Mock()
        assistant.interaction.wait.return_value = LocatedText(
            "Katheryne",
            Match(100, 200, 80, 20, score=0.95),
            "Katheryne",
        )
        assistant._wait_for_talk = Mock(return_value=False)
        return assistant

    def test_default_mode_only_confirms_the_prompt(self):
        assistant = self.make_assistant()

        result = assistant.run(GuildAction.DAILY, timeout=0.2)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.dry_run)
        self.assertEqual(result.option_text, "")
        assistant._wait_for_talk.assert_not_called()
        assistant.device.tap.assert_not_called()

    def test_experimental_mode_never_scans_options_without_talk_confirmation(self):
        assistant = self.make_assistant()

        result = assistant.run(GuildAction.DAILY, timeout=0.2, dry_run=False)

        self.assertIsNone(result)
        assistant._wait_for_talk.assert_called_once_with(0.2)
        assistant.device.tap.assert_not_called()

    def test_unverified_localization_requires_explicit_text(self):
        assistant = self.make_assistant()
        assistant.config.lang = "de"

        with self.assertRaisesRegex(ValueError, "no verified guild localization"):
            assistant.run(GuildAction.EXPEDITION, timeout=0.2)


if __name__ == "__main__":
    unittest.main()
