"""Tests for the OMR spike, using synthetic phone photos (spike/synth.py).

Run from the project root:   python -m unittest spike.test_omr_spike -v
(No Django needed. Not part of `manage.py test`.)
"""
import unittest

import cv2
import numpy as np

from core import sheet_layout as L
from spike import omr_spike as O
from spike import synth as S

LETTERS = "ABCD"


def make_photo(choices, marks, seed=0, version="E7-B", serial=3, mutate=None, **photo_kw):
    """marks: {item: [(choice_index, fill), ...]}. mutate(page) edits the clean page first."""
    rng = np.random.default_rng(seed)
    page = S.render_sheet(choices, version, serial)
    for item, lst in marks.items():
        for choice, fill in lst:
            S.shade(page, item, choice, fill, rng)
    if mutate:
        mutate(page)
    return S.photograph(page, rng, **photo_kw)


def solid_marks(n, seed=1, choices=None):
    rng = np.random.default_rng(seed)
    choices = choices or [4] * n
    truth = [int(rng.integers(0, choices[i])) for i in range(n)]
    marks = {i + 1: [(t, float(rng.uniform(0.7, 0.95)))] for i, t in enumerate(truth)}
    return truth, marks


class ReadingTests(unittest.TestCase):
    def test_reads_every_answer_and_the_qr(self):
        choices = [4] * 30
        truth, marks = solid_marks(30)
        res = O.read_sheet(make_photo(choices, marks), choices)
        self.assertTrue(res.qr_ok)
        self.assertEqual((res.version_code, res.serial), ("E7-B", 3))
        self.assertEqual([r.answer for r in res.items], [LETTERS[t] for t in truth])

    def test_upside_down_and_sideways_photos(self):
        choices = [4] * 25
        truth, marks = solid_marks(25, seed=2)
        for kw in (dict(rotate_deg=180), dict(rot90=1), dict(rot90=3)):
            res = O.read_sheet(make_photo(choices, marks, **kw), choices)
            self.assertEqual([r.answer for r in res.items], [LETTERS[t] for t in truth], kw)

    def test_true_false_items_have_only_two_bubbles(self):
        choices = [4, 2, 4, 2, 4, 4, 4, 2] + [4] * 12
        truth, marks = solid_marks(20, seed=3, choices=choices)
        res = O.read_sheet(make_photo(choices, marks), choices)
        self.assertEqual([r.answer for r in res.items], [LETTERS[t] for t in truth])
        self.assertEqual(len(res.items[1].ratios), 2)

    def test_two_columns_for_a_full_50_item_sheet(self):
        choices = [4] * 50
        truth, marks = solid_marks(50, seed=4)
        res = O.read_sheet(make_photo(choices, marks), choices)
        self.assertEqual([r.answer for r in res.items], [LETTERS[t] for t in truth])


class NeverGuessTests(unittest.TestCase):
    def test_blank_double_faint_and_smudge_are_flagged(self):
        choices = [4] * 20
        _, marks = solid_marks(20, seed=5)
        marks[2] = []                                          # blank
        marks[3] = [(0, 0.9), (2, 0.9)]                        # double mark
        marks[4] = [(1, 0.30)]                                 # faint only
        marks[5] = [(1, 0.9), (3, 0.25)]                       # solid + smudge
        res = O.read_sheet(make_photo(choices, marks), choices)
        status = {r.item: r.status for r in res.items}
        self.assertEqual(status[2], "blank")
        self.assertEqual(status[3], "multiple")
        self.assertEqual(status[4], "ambiguous")
        self.assertEqual(status[5], "ambiguous")
        for r in res.items:
            if r.status != "selected":
                self.assertIsNone(r.answer)                    # no guessed answer

    def test_completely_blank_sheet_is_all_blank(self):
        choices = [4] * 15
        res = O.read_sheet(make_photo(choices, {}), choices)
        self.assertTrue(all(r.status == "blank" for r in res.items))

    def test_light_pencil_throughout_is_still_read(self):
        choices = [4] * 20
        truth, _ = solid_marks(20, seed=6)
        marks = {i + 1: [(t, 0.40)] for i, t in enumerate(truth)}
        res = O.read_sheet(make_photo(choices, marks), choices)
        self.assertEqual([r.answer for r in res.items], [LETTERS[t] for t in truth])


class FailureModeTests(unittest.TestCase):
    def test_missing_corner_marker_is_reported(self):
        choices = [4] * 10
        _, marks = solid_marks(10, seed=7)

        def erase_marker(page):
            m = L.markers()[0]
            (x0, y1), (x1, y0) = [tuple(map(int, L.to_pixel(*p, O.SCALE)))
                                  for p in ((m.x - 3, m.y - 3), (m.x + m.w + 3, m.y + m.h + 3))]
            page[y0:y1, x0:x1] = 255

        with self.assertRaises(O.OMRError):
            O.read_sheet(make_photo(choices, marks, mutate=erase_marker), choices)

    def test_garbage_image_is_reported_not_guessed(self):
        noise = np.random.default_rng(0).integers(0, 255, (1200, 900), dtype=np.uint8)
        with self.assertRaises(O.OMRError):
            O.read_sheet(noise, [4] * 10)

    def test_damaged_qr_falls_back_to_bubble_pattern_with_a_warning(self):
        choices = [4] * 20
        truth, marks = solid_marks(20, seed=8)

        def blank_qr(page):
            q = L.qr_box()
            (x0, y1), (x1, y0) = [tuple(map(int, L.to_pixel(*p, O.SCALE)))
                                  for p in ((q.x, q.y), (q.x + q.w, q.y + q.h))]
            page[y0:y1, x0:x1] = 255

        res = O.read_sheet(make_photo(choices, marks, mutate=blank_qr, rotate_deg=180), choices)
        self.assertFalse(res.qr_ok)
        self.assertTrue(any("manually" in w for w in res.warnings))
        self.assertEqual([r.answer for r in res.items], [LETTERS[t] for t in truth])

    def test_unclear_orientation_is_refused_rather_than_guessed(self):
        choices = [4] * 20
        _, marks = solid_marks(20, seed=9)

        def wipe_grid_and_qr(page):
            q = L.qr_box()
            (x0, y1), (x1, y0) = [tuple(map(int, L.to_pixel(*p, O.SCALE)))
                                  for p in ((q.x, q.y), (q.x + q.w, q.y + q.h))]
            page[y0:y1, x0:x1] = 255
            top = int(L.to_pixel(0, L.GRID_TOP + 20, O.SCALE)[1])
            bottom = int(L.to_pixel(0, 40, O.SCALE)[1])
            page[top:bottom, 80:O.WARP_W - 80] = 255      # erase every ring and mark

        with self.assertRaises(O.OMRError):
            O.read_sheet(make_photo(choices, marks, mutate=wipe_grid_and_qr), choices)


class AccuracyTests(unittest.TestCase):
    def test_no_confident_wrong_answers_across_varied_photos(self):
        conditions = [dict(), dict(tilt=2.0, light=0.4), dict(rotate_deg=8, tilt=1.5),
                      dict(rotate_deg=180), dict(noise=8, blur=1.5)]
        confident_wrong = total = 0
        for seed, kw in enumerate(conditions):
            choices = [4] * 40
            truth, marks = solid_marks(40, seed=100 + seed)
            res = O.read_sheet(make_photo(choices, marks, seed=seed, **kw), choices)
            out = O.compare_to_truth(res.items, [LETTERS[t] for t in truth])
            confident_wrong += out["confident_wrong"]
            total += 40
        self.assertEqual(confident_wrong, 0, f"{confident_wrong} confident-wrong of {total}")


class CompareTests(unittest.TestCase):
    def test_compare_counts_the_three_outcomes(self):
        mk = lambda i, s, a, marked=(): O.ItemResult(i, s, a, list(marked))
        items = [mk(1, "selected", "A"), mk(2, "selected", "B"),
                 mk(3, "multiple", None, "AB"), mk(4, "blank", None)]
        out = O.compare_to_truth(items, ["A", "C", "AB", "-"])
        self.assertEqual(out, {"correct": 3, "flagged": 0, "confident_wrong": 1})


if __name__ == "__main__":
    unittest.main()