import unittest

import numpy as np

from backend.image_cleanup import build_text_mask, remove_text


class ImageCleanupTests(unittest.TestCase):
    def test_mask_is_clipped_to_image(self):
        image = np.zeros((40, 60, 3), dtype=np.uint8)
        mask = build_text_mask(image.shape, [
            {"x": -5, "y": 4, "width": 20, "height": 10}
        ])
        self.assertEqual(mask.shape, (40, 60))
        self.assertTrue(np.any(mask))
        self.assertEqual(int(mask[0, 0]), 0)

    def test_empty_regions_return_unchanged_copy(self):
        image = np.full((12, 12, 3), 127, dtype=np.uint8)
        result = remove_text(image, [])
        self.assertTrue(np.array_equal(image, result))
        self.assertIsNot(image, result)

    def test_group_mask_uses_individual_line_boxes_not_large_group_box(self):
        image_shape = (100, 160, 3)
        mask = build_text_mask(image_shape, [{
            "x": 10, "y": 10, "width": 120, "height": 70,
            "mask_regions": [
                {"x": 15, "y": 15, "width": 35, "height": 10},
                {"x": 15, "y": 34, "width": 40, "height": 10},
            ],
        }])
        self.assertEqual(int(mask[80, 80]), 0)
        self.assertGreater(int(mask[18, 18]), 0)
        self.assertGreater(int(mask[37, 18]), 0)

    def test_invalid_line_box_is_ignored(self):
        image = np.zeros((20, 20, 3), dtype=np.uint8)
        mask = build_text_mask(image.shape, [{"mask_regions": [
            {"x": "bad", "y": 0, "width": 5, "height": 5}
        ]}])
        self.assertFalse(np.any(mask))


if __name__ == "__main__":
    unittest.main()
