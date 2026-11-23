import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from backend.ocr import model_label, normalize_language, recognize_image


class FakeEngine:
    def predict(self, image):
        return [SimpleNamespace(json={
            "res": {
                "rec_polys": [
                    [[20, 30], [90, 30], [90, 52], [20, 52]],
                    [[12, 5], [70, 5], [70, 24], [12, 24]],
                ],
                "rec_texts": ["Second line", "First line"],
                "rec_scores": [0.91, 0.98],
            }
        })]


class OcrTests(unittest.TestCase):
    def test_english_defaults_to_pp_ocrv6(self):
        self.assertEqual(normalize_language("English"), "en")
        self.assertIn("PP-OCRv6", model_label("English"))
        self.assertIn("ONNX Runtime CPU", model_label("English"))

    def test_japanese_and_chinese_use_pp_ocrv6(self):
        self.assertEqual(normalize_language("Japanese"), "japan")
        self.assertIn("PP-OCRv6", model_label("Chinese"))

    def test_korean_and_thai_use_supported_legacy_language_models(self):
        self.assertIn("PP-OCRv5", model_label("Korean"))
        self.assertIn("PP-OCRv5", model_label("Thai"))

    def test_regions_are_normalized_and_sorted_in_reading_order(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        with patch("backend.ocr._build_engine", return_value=FakeEngine()):
            regions = recognize_image(image, "English")
        self.assertEqual([item["text"] for item in regions], ["First line", "Second line"])
        self.assertEqual([item["reading_order"] for item in regions], [1, 2])
        self.assertEqual(regions[0]["x"], 12)
        self.assertAlmostEqual(regions[0]["confidence"], 0.98)

    def test_empty_image_is_rejected(self):
        with self.assertRaises(ValueError):
            recognize_image(np.zeros((0, 0, 3), dtype=np.uint8), "English")


if __name__ == "__main__":
    unittest.main()
