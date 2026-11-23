import unittest

import numpy as np

from backend.image_inpainting import MODEL_SPECS, _pad_to_multiple


class InpaintingModelTests(unittest.TestCase):
    def test_both_manga_models_are_registered(self):
        self.assertIn("lama_manga", MODEL_SPECS)
        self.assertIn("aot_gan", MODEL_SPECS)

    def test_padding_preserves_original_dimensions(self):
        image = np.zeros((5, 7, 3), dtype=np.uint8)
        padded, original_size = _pad_to_multiple(image, 8)
        self.assertEqual(padded.shape, (8, 8, 3))
        self.assertEqual(original_size, (5, 7))

    def test_mask_padding_preserves_two_dimensional_shape(self):
        mask = np.zeros((9, 11), dtype=np.uint8)
        padded, original_size = _pad_to_multiple(mask, 4)
        self.assertEqual(padded.shape, (12, 12))
        self.assertEqual(original_size, (9, 11))


if __name__ == "__main__":
    unittest.main()
