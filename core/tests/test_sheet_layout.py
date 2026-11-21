import itertools
import math
import unittest

from core import sheet_layout as L


class BubbleGeometryTests(unittest.TestCase):
    def setUp(self):
        self.full = L.all_bubbles([4] * 50)

    def test_full_sheet_has_200_bubbles(self):
        self.assertEqual(len(self.full), 200)

    def test_bubbles_never_overlap_and_keep_a_gap(self):
        for a, b in itertools.combinations(self.full, 2):
            d = math.hypot(a.cx - b.cx, a.cy - b.cy)
            self.assertGreaterEqual(d, 2 * L.BUBBLE_R + 8, (a.item, a.choice, b.item, b.choice))

    def test_bubbles_stay_inside_the_page(self):
        for b in self.full:
            self.assertGreater(b.cx - b.r, 0)
            self.assertLess(b.cx + b.r, L.PAGE_W)
            self.assertGreater(b.cy - b.r, 0)
            self.assertLess(b.cy + b.r, L.PAGE_H)

    def test_bubbles_clear_markers_and_qr_box(self):
        keepout = L.markers() + [L.qr_box()]
        for b in self.full:
            for r in keepout:
                self.assertFalse(b.rect.intersects(r, pad=10), (b.item, b.choice))

    def test_markers_are_in_the_four_corners(self):
        m = L.markers()
        self.assertEqual(len(m), 4)
        self.assertEqual(len({(r.x, r.y) for r in m}), 4)
        for r in m:
            self.assertGreaterEqual(r.x, 0)
            self.assertLessEqual(r.x + r.w, L.PAGE_W)
            self.assertGreaterEqual(r.y, 0)
            self.assertLessEqual(r.y + r.h, L.PAGE_H)

    def test_item_to_column_and_row(self):
        self.assertEqual(L.column_and_row(1), (0, 0))
        self.assertEqual(L.column_and_row(25), (0, 24))
        self.assertEqual(L.column_and_row(26), (1, 0))
        self.assertEqual(L.column_and_row(50), (1, 24))

    def test_rows_go_down_and_columns_go_right(self):
        self.assertAlmostEqual(L.bubble(1, 0).cy - L.bubble(2, 0).cy, L.ROW_PITCH)
        self.assertEqual(L.bubble(26, 0).cy, L.bubble(1, 0).cy)
        self.assertGreater(L.bubble(26, 0).cx, L.bubble(1, 3).cx)
        self.assertAlmostEqual(L.bubble(1, 1).cx - L.bubble(1, 0).cx, L.CHOICE_PITCH)

    def test_true_false_items_only_get_two_bubbles(self):
        self.assertEqual(L.choices_for("TF"), 2)
        self.assertEqual(L.choices_for("MC"), 4)
        self.assertEqual(len(L.all_bubbles([2, 4, 2])), 8)

    def test_out_of_range_input_is_rejected(self):
        for bad in (0, 51):
            with self.assertRaises(ValueError):
                L.column_and_row(bad)
        with self.assertRaises(ValueError):
            L.all_bubbles([4] * 51)
        with self.assertRaises(ValueError):
            L.all_bubbles([])
        with self.assertRaises(ValueError):
            L.bubble(1, 4)

    def test_one_column_for_25_items_two_for_more(self):
        self.assertEqual(L.num_columns(25), 1)
        self.assertEqual(L.num_columns(26), 2)


class PayloadTests(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(L.decode_payload(L.encode_payload("E12-A", 7)), ("E12-A", 7))

    def test_tampering_is_detected(self):
        good = L.encode_payload("E12-A", 7)
        self.assertIsNone(L.decode_payload(good.replace("E12-A", "E12-B")))
        self.assertIsNone(L.decode_payload(good.replace("|7|", "|8|")))

    def test_garbage_is_rejected(self):
        for bad in ("", None, "hello", "EG1|E12-A|7", "XX1|E12-A|7|0000", "EG1|E12-A|x|0000"):
            self.assertIsNone(L.decode_payload(bad))

    def test_bad_inputs_to_encode(self):
        with self.assertRaises(ValueError):
            L.encode_payload("A|B", 1)
        with self.assertRaises(ValueError):
            L.encode_payload("E1-A", 0)