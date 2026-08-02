from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from bgia.autoskip import AutoSkipTask, OptionOutcome
from bgia.config import Config
from bgia.game import GameWindow
from bgia.vision import Match


class FakeOcr:
    def __init__(self, results):
        self.results = results

    def recognize(self, _image, upscale=None):
        return self.results


class AutoSkipOptionTests(unittest.TestCase):
    def make_task(self) -> AutoSkipTask:
        task = AutoSkipTask.__new__(AutoSkipTask)
        task.config = Config()
        task.window = GameWindow(0, 0, 1920, 1080, "test", False)
        task._paused_reason = None
        task._last_option_click = 0.0
        return task

    def test_standard_roi_matches_bettergi(self):
        task = self.make_task()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.assertEqual(task._standard_option_roi(frame), (960, 90, 640, 980))

    def test_short_cjk_is_preserved_and_short_ascii_is_filtered(self):
        task = self.make_task()
        task.ocr = FakeOcr(
            [
                Match(10, 10, 20, 20, text="是"),
                Match(10, 100, 20, 20, text="OK"),
            ]
        )
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        options = task._read_options(frame, (960, 90, 500, 300))
        self.assertEqual([option.text for option in options], ["是"])

    def test_orange_ratio_is_forwarded(self):
        task = self.make_task()
        task.config.orange_ratio = 0.23
        task.ocr = FakeOcr([Match(10, 10, 50, 20, text="Continue")])
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        with patch("bgia.autoskip.is_orange_option", return_value=False) as orange:
            task._read_options(frame, (960, 90, 500, 300))
        orange.assert_called_once()
        self.assertEqual(orange.call_args.args[1], 0.23)

    def test_none_mode_blocks_exclamation_without_tapping(self):
        task = self.make_task()
        task.config.option_mode = "none"
        task.config.choose_option = True
        task._find = lambda _frame, name, **_kwargs: Match(10, 10, 20, 20) if name == "icon_exclamation.png" else None
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        outcome = task._handle_options(frame)
        self.assertEqual(outcome, OptionOutcome.PAUSED)

    def test_positional_modes_are_shared(self):
        items = ["a", "b", "c"]
        self.assertEqual(AutoSkipTask._pick_position(items, "first"), 0)
        self.assertEqual(AutoSkipTask._pick_position(items, "second"), 1)
        self.assertEqual(AutoSkipTask._pick_position(items, "last"), 2)

    def test_pause_keyword_wins_over_a_conflicting_builtin_selection(self):
        task = self.make_task()
        task.config.select_keywords = ["abandon"]
        task.config.pause_keywords = ["abandon"]
        result = task._decide_option([Match(0, 0, 100, 20, text="Abandon quest")])
        self.assertIsNone(result)

    def test_continue_indicator_area_scales_with_resolution(self):
        task = self.make_task()
        large = np.zeros((1080, 1920, 3), dtype=np.uint8)
        large[950:961, 955:966] = 255
        self.assertTrue(task._has_continue_indicator(large))

        task.window = GameWindow(0, 0, 1280, 720, "test", False)
        small = np.zeros((720, 1280, 3), dtype=np.uint8)
        small[633:640, 637:644] = 255
        self.assertTrue(task._has_continue_indicator(small))

    def test_continue_keyword_matching_is_case_insensitive(self):
        task = self.make_task()
        task._kw = {"continue_": ["continue"]}
        task.ocr = FakeOcr([Match(10, 10, 100, 20, score=0.95, text="Tap to Continue")])
        task._find = lambda *_args, **_kwargs: None
        task._has_continue_indicator = lambda _frame: False
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.assertTrue(task._is_click_continue(frame))


if __name__ == "__main__":
    unittest.main()
