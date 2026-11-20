import unittest

from core.combinatorics import (combinations, format_big_number,
                                permutations, selection_count)


class CombinatoricsTests(unittest.TestCase):
    def test_combinations_known_values(self):
        self.assertEqual(combinations(5, 2), 10)
        self.assertEqual(combinations(10, 0), 1)
        self.assertEqual(combinations(10, 10), 1)

    def test_cannot_choose_more_than_available(self):
        self.assertEqual(combinations(3, 5), 0)

    def test_permutations(self):
        self.assertEqual(permutations(4), 24)      # 4! orderings of A-D
        self.assertEqual(permutations(5, 2), 20)

    def test_negative_input_rejected(self):
        with self.assertRaises(ValueError):
            combinations(-1, 2)
        with self.assertRaises(ValueError):
            combinations(5, -2)

    def test_non_integer_rejected(self):
        with self.assertRaises(ValueError):
            combinations(5.5, 2)

    def test_selection_count_is_product_of_groups(self):
        # C(10,2) * C(6,3) = 45 * 20 = 900
        self.assertEqual(selection_count([(10, 2), (6, 3)]), 900)

    def test_selection_count_zero_when_a_group_is_short(self):
        self.assertEqual(selection_count([(10, 2), (1, 3)]), 0)

    def test_format_big_number(self):
        self.assertEqual(format_big_number(1234), "1,234")
        self.assertEqual(format_big_number(10 ** 25), "1.00 x 10^25")


if __name__ == "__main__":
    unittest.main()