from __future__ import annotations

import unittest
from unittest.mock import Mock

import numpy as np

from bgia.config import Config
from bgia.game import GameWindow
from bgia.interaction import InteractionPromptTask, LocatedText, OcrTextLocator, normalize_ui_text
from bgia.vision import Match


class FakeOcr:
    def __init__(self, results):
        self.results = results

    def recognize(self, _image, upscale=None):
        return self.results


class FakeDevice:
    def __init__(self):
        self.taps = []

    def tap(self, x, y):
        self.taps.append((x, y))


class InteractionTests(unittest.TestCase):
    def test_normalization_removes_ui_separators(self):
        self.assertEqual(normalize_ui_text(" > Katheryne · "), "katheryne")
        self.assertEqual(normalize_ui_text("挪德-卡莱"), "挪德卡莱")

    def test_locator_checks_all_ocr_boxes(self):
        ocr = FakeOcr(
            [
                Match(1, 2, 10, 10, score=0.95, text="Other"),
                Match(20, 30, 80, 20, score=0.95, text="> Katheryne"),
            ]
        )
        frame = np.zeros((200, 400, 3), dtype=np.uint8)
        result = OcrTextLocator(ocr).find(frame, ["Katheryne"], (100, 20, 200, 150))
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.match.x, 120)
        self.assertEqual(result.match.y, 50)

    def test_locator_rejects_substrings_low_confidence_and_ambiguous_matches(self):
        frame = np.zeros((200, 400, 3), dtype=np.uint8)
        low = OcrTextLocator(FakeOcr([Match(1, 2, 10, 10, score=0.2, text="Katheryne")]))
        self.assertIsNone(low.find(frame, ["Katheryne"], (0, 0, 400, 200)))

        substring = OcrTextLocator(
            FakeOcr([Match(1, 2, 100, 10, score=0.95, text="Katheryne Reward")])
        )
        self.assertIsNone(substring.find(frame, ["Katheryne"], (0, 0, 400, 200)))

        duplicate = OcrTextLocator(
            FakeOcr(
                [
                    Match(1, 2, 80, 10, score=0.95, text="Katheryne"),
                    Match(1, 40, 80, 10, score=0.96, text="Katheryne"),
                ]
            )
        )
        self.assertIsNone(
            duplicate.find(
                frame,
                ["Katheryne"],
                (0, 0, 400, 200),
                reject_ambiguous=True,
            )
        )

    def make_prompt_task(self, results):
        task = InteractionPromptTask.__new__(InteractionPromptTask)
        task.device = FakeDevice()
        task.config = Config(interval=0.05, click_delay=0.0)
        task.window = GameWindow(10, 20, 1920, 1080, "test", False)
        task.capture = Mock(return_value=np.zeros((1080, 1920, 3), dtype=np.uint8))
        task.locator = Mock()
        task.locator.find.side_effect = results
        return task

    def test_prompt_observation_requires_two_frames_and_does_not_tap_by_default(self):
        found = LocatedText("Katheryne", Match(100, 200, 80, 20, score=0.95), "Katheryne")
        task = self.make_prompt_task([found, found])

        result = task.wait(["Katheryne"], timeout=0.2)

        self.assertEqual(result, found)
        self.assertEqual(task.locator.find.call_count, 2)
        self.assertEqual(task.device.taps, [])

    def test_experimental_prompt_tap_happens_only_after_stable_confirmation(self):
        first = LocatedText("Katheryne", Match(100, 200, 80, 20, score=0.95), "Katheryne")
        moved = LocatedText("Katheryne", Match(500, 500, 80, 20, score=0.95), "Katheryne")
        task = self.make_prompt_task([first, moved, moved])

        result = task.wait(["Katheryne"], timeout=0.3, dry_run=False)

        self.assertEqual(result, moved)
        self.assertEqual(task.device.taps, [(550, 530)])


if __name__ == "__main__":
    unittest.main()
