import unittest

from backend.region_grouping import group_text_regions


class RegionGroupingTests(unittest.TestCase):
    def test_adjacent_lines_with_shared_alignment_are_grouped(self):
        regions = [
            {"index": 0, "x": 20, "y": 20, "width": 70, "height": 15, "text": "First", "confidence": .9},
            {"index": 1, "x": 25, "y": 39, "width": 65, "height": 15, "text": "Second", "confidence": .8},
            {"index": 2, "x": 180, "y": 20, "width": 60, "height": 15, "text": "Other bubble", "confidence": .9},
        ]
        groups = group_text_regions(regions)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["region_indices"], [0, 1])
        self.assertEqual(groups[0]["text"], "First\\nSecond")

    def test_empty_and_invalid_regions_are_ignored(self):
        self.assertEqual(group_text_regions([]), [])
        self.assertEqual(group_text_regions([{"x": 1, "y": 2, "width": 0, "height": 4}]), [])

    def test_single_region_is_preserved(self):
        regions = [{"index": 4, "x": 5, "y": 6, "width": 30, "height": 12, "text": "Hello"}]
        groups = group_text_regions(regions)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["region_indices"], [4])


if __name__ == "__main__":
    unittest.main()
