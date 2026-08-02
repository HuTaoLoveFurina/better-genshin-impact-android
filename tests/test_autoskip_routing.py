from __future__ import annotations

import unittest
from unittest.mock import Mock

import numpy as np

from bgia.autoskip import AutoSkipTask, OptionOutcome
from bgia.config import Config
from bgia.game import GameWindow
from bgia.talk_state import TalkEvidence, TalkState


class FakeDevice:
    def __init__(self, frame: np.ndarray) -> None:
        self.frame = frame
        self.taps: list[tuple[int, int]] = []

    def screencap(self) -> np.ndarray:
        return self.frame

    def tap(self, x: int, y: int) -> None:
        self.taps.append((x, y))


class AutoSkipRoutingTests(unittest.TestCase):
    def make_task(self, talk: TalkState) -> AutoSkipTask:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        task = AutoSkipTask.__new__(AutoSkipTask)
        task.device = FakeDevice(frame)
        task.config = Config()
        task.window = GameWindow(0, 0, 1920, 1080, "test", False)
        task._frame_index = 0
        task._last_frame = None
        task._last_talk_evidence = TalkEvidence.NONE
        task._talk_detector = Mock()
        task._talk_detector.observe.return_value = talk
        task._handle_hangout = Mock(return_value=False)
        task._has_explicit_extended_options = Mock(return_value=False)
        task._handle_options = Mock(return_value=OptionOutcome.NO_OPTION)
        task._handle_playing = Mock(return_value=False)
        task._handle_popup = Mock(return_value=False)
        task._handle_click_continue = Mock(return_value=False)
        task._handle_black_screen = Mock(return_value=False)
        return task

    def test_paused_option_stops_quick_advance(self):
        talk = TalkState(True, True, TalkEvidence.DISABLED_UI)
        task = self.make_task(talk)
        task._handle_options.return_value = OptionOutcome.PAUSED

        task.tick()

        task._handle_playing.assert_not_called()
        task._handle_black_screen.assert_not_called()
        self.assertEqual(task.device.taps, [])

    def test_inactive_ordinary_menu_never_runs_option_handling(self):
        task = self.make_task(TalkState(False, False, TalkEvidence.NONE))

        task.tick()

        task._handle_options.assert_not_called()
        task._handle_popup.assert_not_called()
        task._handle_click_continue.assert_not_called()

    def test_active_talk_without_options_advances_once(self):
        task = self.make_task(TalkState(True, True, TalkEvidence.DISABLED_UI))
        task._handle_playing.return_value = True

        task.tick()

        task._handle_options.assert_called_once()
        task._handle_playing.assert_called_once()
        task._handle_black_screen.assert_not_called()

    def test_grace_handlers_run_before_black_screen(self):
        task = self.make_task(TalkState(False, True, TalkEvidence.NONE))
        task._handle_click_continue.return_value = True

        task.tick()

        task._handle_popup.assert_called_once()
        task._handle_click_continue.assert_called_once()
        task._handle_black_screen.assert_not_called()

    def test_black_screen_runs_only_after_inactive_handlers_decline(self):
        task = self.make_task(TalkState(False, True, TalkEvidence.NONE))

        task.tick()

        task._handle_popup.assert_called_once()
        task._handle_click_continue.assert_called_once()
        task._handle_black_screen.assert_called_once()

    def test_grace_expiry_disables_popup_and_continue_routes(self):
        task = self.make_task(TalkState(False, False, TalkEvidence.NONE))

        task.tick()

        task._handle_popup.assert_not_called()
        task._handle_click_continue.assert_not_called()
        task._handle_black_screen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
