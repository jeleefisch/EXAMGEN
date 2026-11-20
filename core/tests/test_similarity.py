import unittest

from core.similarity import compare, jaccard, pairwise_overlaps, summarize


class JaccardTests(unittest.TestCase):
    def test_example_from_project_spec(self):
        # 20 questions each, 5 shared, 35 unique in total.
        a = set(range(0, 20))
        b = set(range(15, 35))
        self.assertAlmostEqual(jaccard(a, b), 5 / 35)

    def test_identical_sets(self):
        self.assertEqual(jaccard({1, 2, 3}, {1, 2, 3}), 1.0)

    def test_disjoint_sets(self):
        self.assertEqual(jaccard({1, 2}, {3, 4}), 0.0)

    def test_both_empty_is_defined_as_identical(self):
        self.assertEqual(jaccard(set(), set()), 1.0)

    def test_order_and_duplicates_do_not_matter(self):
        self.assertEqual(jaccard([1, 1, 2], [2, 1]), 1.0)


class CompareTests(unittest.TestCase):
    def test_spec_numbers_and_percent(self):
        r = compare("A", range(0, 20), "B", range(15, 35))
        self.assertEqual((r.shared, r.union), (5, 35))
        self.assertEqual(r.percent, 14.29)


class PairwiseTests(unittest.TestCase):
    def test_three_versions_make_three_pairs(self):
        versions = {"A": {1, 2}, "B": {2, 3}, "C": {1, 3}}
        results = pairwise_overlaps(versions)
        self.assertEqual(len(results), 3)
        stats = summarize(results)
        self.assertEqual(stats["pairs"], 3)
        self.assertAlmostEqual(stats["mean_jaccard"], 1 / 3)

    def test_summarize_empty(self):
        self.assertIsNone(summarize([]))


if __name__ == "__main__":
    unittest.main()