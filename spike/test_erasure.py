import unittest

from spike.erasure import flag_erasures
from spike.omr_spike import ItemResult, SheetResult, compare_to_truth


def _sheet(items):
    return SheetResult(True, "E1-A", 1, 0, items, {}, [])


class ErasureTests(unittest.TestCase):
    def test_mark_beside_whiteout_is_flagged(self):
        r = ItemResult(6, "selected", "B", ["B"], [], [-0.05, 0.719, -0.001, 0.012], [])
        res = _sheet([r])
        self.assertEqual(flag_erasures(res), 1)
        self.assertEqual(r.status, "ambiguous")
        self.assertIsNone(r.answer)
        self.assertEqual(compare_to_truth([r], ["B"])["flagged"], 1)
        self.assertTrue(res.warnings)

    def test_normal_row_is_untouched(self):
        r = ItemResult(5, "selected", "B", ["B"], [], [0.0, 0.802, -0.001, 0.013], [])
        self.assertEqual(flag_erasures(_sheet([r])), 0)
        self.assertEqual(r.status, "selected")

    def test_blank_row_is_untouched(self):
        r = ItemResult(2, "blank", None, [], [], [0.0, 0.017, 0.0, 0.013], [])
        self.assertEqual(flag_erasures(_sheet([r])), 0)


if __name__ == "__main__":
    unittest.main()