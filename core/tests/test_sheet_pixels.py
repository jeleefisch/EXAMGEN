import unittest

from core import sheet_layout as L


class ToPixelTests(unittest.TestCase):
    def test_page_corners_map_to_image_corners(self):
        s = 150 / 72
        self.assertEqual(L.to_pixel(0, L.PAGE_H, s), (0.0, 0.0))            # top-left
        x, y = L.to_pixel(L.PAGE_W, 0, s)                                   # bottom-right
        self.assertAlmostEqual(x, L.PAGE_W * s)
        self.assertAlmostEqual(y, L.PAGE_H * s)

    def test_y_is_flipped(self):
        low = L.to_pixel(100, 50, 1.0)[1]
        high = L.to_pixel(100, 700, 1.0)[1]
        self.assertGreater(low, high)    # lower on the page = larger pixel row

    def test_first_item_is_near_the_top_of_the_grid(self):
        first = L.bubble(1, 0)
        last = L.bubble(25, 0)
        self.assertLess(L.to_pixel(first.cx, first.cy, 1.0)[1],
                        L.to_pixel(last.cx, last.cy, 1.0)[1])

    def test_scale_multiplies_both_axes(self):
        self.assertEqual(L.to_pixel(10, L.PAGE_H - 20, 2.0), (20.0, 40.0))


if __name__ == "__main__":
    unittest.main()