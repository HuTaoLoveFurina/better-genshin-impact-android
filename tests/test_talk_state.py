from __future__ import annotations

import unittest

import numpy as np

from bgia.talk_state import TalkEvidence, TalkStateDetector
from bgia.vision import Match


class FakeOcr:
    def __init__(self, results=None):
        self.results = results or []
        self.calls = 0

    def recognize(self, _image):
        self.calls += 1
        return self.results


class TalkStateDetectorTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    def test_disabled_ui_has_priority_and_skips_ocr(self):
        ocr = FakeOcr()
        detector = TalkStateDetector(ocr, ["playing"])
        calls = []

        def fake_match(_frame, name, _scale, roi):
            calls.append((name, roi))
            return name == "disabled_ui.png"

        detector._match = fake_match
        state = detector.observe(self.frame, 1.0, now=10.0)
        self.assertTrue(state.active)
        self.assertEqual(state.evidence, TalkEvidence.DISABLED_UI)
        self.assertEqual(calls, [("disabled_ui.png", (0, 0, 640, 135))])
        self.assertEqual(ocr.calls, 0)

    def test_legacy_template_fallback(self):
        detector = TalkStateDetector(FakeOcr(), ["playing"])
        detector._match = lambda _frame, name, _scale, _roi: name == "stop_auto.png"
        state = detector.observe(self.frame, 1.0, now=1.0)
        self.assertEqual(state.evidence, TalkEvidence.LEGACY_STOP_AUTO)

    def test_legacy_detection_can_be_disabled(self):
        ocr = FakeOcr()
        detector = TalkStateDetector(ocr, ["playing"], legacy_fallback=False)
        detector._match = lambda *_args: False
        state = detector.observe(self.frame, 1.0, now=1.0)
        self.assertFalse(state.active)
        self.assertEqual(ocr.calls, 0)

    def test_legacy_ocr_requires_confident_text(self):
        low = TalkStateDetector(
            FakeOcr([Match(0, 0, 80, 20, score=0.2, text="Playing")]),
            ["playing"],
        )
        low._match = lambda *_args: False
        self.assertEqual(low.detect_active(self.frame, 1.0), TalkEvidence.NONE)

        high = TalkStateDetector(
            FakeOcr([Match(0, 0, 80, 20, score=0.95, text="Playing")]),
            ["playing"],
        )
        high._match = lambda *_args: False
        self.assertEqual(high.detect_active(self.frame, 1.0), TalkEvidence.LEGACY_PLAYING_OCR)

    def test_grace_window_uses_supplied_monotonic_time(self):
        detector = TalkStateDetector(FakeOcr(), [], grace_seconds=10.0)
        active = True
        detector._match = lambda _frame, name, _scale, _roi: active and name == "disabled_ui.png"
        self.assertTrue(detector.observe(self.frame, 1.0, now=100.0).in_grace)
        active = False
        self.assertTrue(detector.observe(self.frame, 1.0, now=109.99).in_grace)
        self.assertFalse(detector.observe(self.frame, 1.0, now=110.01).in_grace)


if __name__ == "__main__":
    unittest.main()
