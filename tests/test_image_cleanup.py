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


if __name__ == "__main__":
    unittest.main()
