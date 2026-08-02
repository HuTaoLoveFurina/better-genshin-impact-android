from __future__ import annotations

import unittest
from unittest.mock import Mock

import numpy as np

from bgia.config import Config
from bgia.game import GameWindow
from bgia.teleport import (
    MapCandidate,
    MapUiRecognizer,
    QuickTeleportStatus,
    QuickTeleportTask,
    missing_quick_teleport_assets,
)
from bgia.vision import Match


class FakeOcr:
    def recognize(self, _image, upscale=None):
        return [Match(0, 0, 100, 20, score=0.95, text="> Mondstadt")]


class TeleportTests(unittest.TestCase):
    def test_required_assets_are_packaged(self):
        self.assertEqual(missing_quick_teleport_assets(), [])

    def test_candidate_roi_scales_from_1920_baseline(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.assertEqual(MapUiRecognizer.candidate_roi(frame, 1.0), (1270, 100, 50, 880))
        small = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.assertEqual(MapUiRecognizer.candidate_roi(small, 2 / 3), (847, 67, 33, 587))

    def test_candidate_text_is_read_from_near_white_mask(self):
        recognizer = MapUiRecognizer(FakeOcr())
        icon = Match(1270, 100, 30, 43, score=0.9)
        recognizer._icon_matches = lambda _frame, _scale: [("TeleportWaypoint", icon)]
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame[92:159, 1300:1500] = 255
        candidates = recognizer.candidates(frame, 1.0)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].text, "> Mondstadt")
        self.assertEqual(candidates[0].click, (1400, 121))

    def make_task(self):
        task = QuickTeleportTask.__new__(QuickTeleportTask)
        task.config = Config(click_delay=0.0)
        task.window = GameWindow(0, 0, 1920, 1080, "test", False)
        task.recognizer = Mock()
        task._capture = Mock(return_value=np.zeros((1080, 1920, 3), dtype=np.uint8))
        task._tap = Mock()
        return task

    def test_default_mode_reports_visible_button_without_tapping(self):
        task = self.make_task()
        task.recognizer.is_big_map.return_value = True
        task.recognizer.teleport_button.return_value = Match(1450, 980, 80, 50, score=0.95)

        result = task.run(timeout=0.2)

        self.assertEqual(result.status, QuickTeleportStatus.DRY_RUN)
        task._tap.assert_not_called()

    def test_live_mode_requires_two_map_absent_frames_after_tap(self):
        task = self.make_task()
        task.recognizer.is_big_map.side_effect = [True, True, False, False]
        task.recognizer.teleport_button.return_value = Match(1450, 980, 80, 50, score=0.95)

        result = task.run(timeout=0.5, dry_run=False)

        self.assertEqual(result.status, QuickTeleportStatus.MAP_CLOSED)
        task._tap.assert_called_once()

    def test_duplicate_visible_targets_are_rejected(self):
        task = self.make_task()
        task.recognizer.is_big_map.return_value = True
        task.recognizer.teleport_button.return_value = None
        task.recognizer.candidate_list_blocked.return_value = False
        icon = Match(1270, 100, 30, 43, score=0.95)
        task.recognizer.candidates.return_value = [
            MapCandidate("TeleportWaypoint", icon, "Teleport Waypoint", (1400, 121)),
            MapCandidate("TeleportWaypoint", Match(1270, 160, 30, 43, score=0.95), "Teleport Waypoint", (1400, 181)),
        ]

        result = task.run(candidate_name="Teleport Waypoint", timeout=0.2)

        self.assertEqual(result.status, QuickTeleportStatus.AMBIGUOUS_TARGET)
        task._tap.assert_not_called()

    def test_unsafe_map_threshold_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "quick_teleport_threshold"):
            Config(quick_teleport_threshold=0.2).validate()


if __name__ == "__main__":
    unittest.main()
