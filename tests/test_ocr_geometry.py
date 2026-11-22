import unittest

import numpy as np

from backend.ocr import _as_list, _box_from_polygon


class OCRGeometryTests(unittest.TestCase):
    def test_polygon_becomes_xywh_box(self):
        polygon = np.array([[10.2, 20.4], [40.8, 20.4], [40.8, 35.9], [10.2, 35.9]])
        self.assertEqual(_box_from_polygon(polygon), (10, 20, 31, 16))

    def test_numpy_result_arrays_are_converted(self):
        values = np.array([[1, 2], [3, 4]])
        self.assertEqual(_as_list(values), [[1, 2], [3, 4]])


if __name__ == "__main__":
    unittest.main()
