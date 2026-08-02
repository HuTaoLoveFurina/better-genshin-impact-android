from __future__ import annotations

import sys
import types
import unittest
from enum import Enum
from unittest.mock import patch

from bgia.vision import OcrEngine


class OcrEngineTests(unittest.TestCase):
    def test_rapidocr_v3_receives_namespaced_language_parameter(self):
        calls = []

        class FakeOcrVersion(Enum):
            PPOCRV4 = "PP-OCRv4"

        class FakeModelType(Enum):
            MOBILE = "mobile"

        class SpyRapidOcr:
            def __init__(self, *args, **kwargs):
                calls.append((args, kwargs))

        fake_module = types.SimpleNamespace(
            RapidOCR=SpyRapidOcr,
            OCRVersion=FakeOcrVersion,
            ModelType=FakeModelType,
        )
        with patch.dict(sys.modules, {"rapidocr": fake_module}):
            engine = OcrEngine(lang="japan")
            self.assertTrue(engine._ensure())
        self.assertEqual(
            calls,
            [
                (
                    (),
                    {
                        "params": {
                            "Rec.ocr_version": FakeOcrVersion.PPOCRV4,
                            "Rec.model_type": FakeModelType.MOBILE,
                            "Rec.lang_type": "japan",
                        }
                    },
                )
            ],
        )

    def test_installed_rapidocr_resolves_all_mapped_recognition_families(self):
        try:
            from rapidocr.inference_engine.base import FileInfo, InferSession
            from rapidocr.utils.typings import EngineType, ModelType, OCRVersion, TaskType
        except ImportError:
            self.skipTest("rapidocr is not installed")

        for lang in ("ch", "chinese_cht", "japan", "korean", "en", "latin", "cyrillic"):
            with self.subTest(lang=lang):
                model = InferSession.get_model_url(
                    FileInfo(
                        EngineType.ONNXRUNTIME,
                        OCRVersion.PPOCRV4,
                        TaskType.REC,
                        lang,
                        ModelType.MOBILE,
                    )
                )
                self.assertIn("model_dir", model)


if __name__ == "__main__":
    unittest.main()
