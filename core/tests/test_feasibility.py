import random
import unittest
from itertools import combinations

from core.generation.feasibility import check_feasibility

EASY, MOD, HARD = "Easy", "Moderate", "Difficult"
DIFFS = (EASY, MOD, HARD)


def rich_bank(topics, per_cell=10):
    return {(t, d): per_cell for t in topics for d in DIFFS}


def assert_valid_allocation(test, result, available, topic_req, diff_req):
    alloc = result.allocation
    for (t, d), n in alloc.items():
        test.assertGreaterEqual(n, 0)
        test.assertLessEqual(n, available.get((t, d), 0))
    for t, need in topic_req.items():
        test.assertEqual(sum(alloc[(t, d)] for d in diff_req), need)
    for d, need in diff_req.items():
        test.assertEqual(sum(alloc[(t, d)] for t in topic_req), need)


class SpecExampleTests(unittest.TestCase):
    def setUp(self):
        self.topics = {"A": 5, "B": 7, "C": 8}
        self.diffs = {EASY: 6, MOD: 8, HARD: 6}
        self.bank = rich_bank(self.topics)

    def test_spec_example_is_feasible(self):
        r = check_feasibility(self.bank, self.topics, self.diffs, 20)
        self.assertTrue(r.feasible)
        self.assertEqual(r.problems, [])
        assert_valid_allocation(self, r, self.bank, self.topics, self.diffs)

    def test_random_allocations_always_valid_and_varied(self):
        seen = set()
        for seed in range(60):
            r = check_feasibility(self.bank, self.topics, self.diffs, 20,
                                  rng=random.Random(seed))
            self.assertTrue(r.feasible)
            assert_valid_allocation(self, r, self.bank, self.topics, self.diffs)
            seen.add(tuple(sorted(r.allocation.items())))
        self.assertGreater(len(seen), 1)


class HiddenProblemTests(unittest.TestCase):
    """The case that per-topic and per-difficulty checks both miss."""

    def test_topic_a_all_difficult_but_few_difficult_allowed(self):
        bank = {("A", HARD): 10,
                ("B", EASY): 10, ("B", MOD): 10, ("B", HARD): 10}
        topics = {"A": 5, "B": 5}
        diffs = {EASY: 4, MOD: 4, HARD: 2}
        r = check_feasibility(bank, topics, diffs, 10)
        self.assertFalse(r.feasible)
        self.assertEqual(len(r.problems), 1)
        self.assertIn("'A'", r.problems[0])
        self.assertEqual(r.bottleneck["topics"], ["A"])
        self.assertEqual(r.bottleneck["need"], 5)
        self.assertEqual(r.bottleneck["max_supply"], 2)


class SimpleProblemTests(unittest.TestCase):
    def test_topic_sum_mismatch(self):
        bank = rich_bank(["A", "B"])
        r = check_feasibility(bank, {"A": 5, "B": 4}, {EASY: 3, MOD: 3, HARD: 3}, 10)
        self.assertFalse(r.feasible)
        self.assertIn("topic quotas add up to 9", r.problems[0])

    def test_difficulty_sum_mismatch(self):
        bank = rich_bank(["A", "B"])
        r = check_feasibility(bank, {"A": 5, "B": 5}, {EASY: 3, MOD: 3, HARD: 3}, 10)
        self.assertFalse(r.feasible)
        self.assertIn("difficulty counts add up to 9", r.problems[0])

    def test_topic_shortage(self):
        bank = {("A", EASY): 2, ("B", EASY): 10, ("B", MOD): 10, ("B", HARD): 10}
        r = check_feasibility(bank, {"A": 5, "B": 5},
                              {EASY: 4, MOD: 3, HARD: 3}, 10)
        self.assertFalse(r.feasible)
        self.assertTrue(any("Topic 'A' needs 5" in p and "only 2" in p
                            for p in r.problems))

    def test_difficulty_shortage(self):
        bank = {("A", EASY): 10, ("A", MOD): 10, ("A", HARD): 1,
                ("B", EASY): 10, ("B", MOD): 10}
        r = check_feasibility(bank, {"A": 5, "B": 5},
                              {EASY: 3, MOD: 3, HARD: 4}, 10)
        self.assertFalse(r.feasible)
        self.assertTrue(any("4 Difficult" in p and "only 1" in p
                            for p in r.problems))

    def test_zero_questions_rejected(self):
        r = check_feasibility({}, {}, {}, 0)
        self.assertFalse(r.feasible)

    def test_negative_numbers_raise(self):
        with self.assertRaises(ValueError):
            check_feasibility({("A", EASY): -1}, {"A": 1}, {EASY: 1}, 1)

    def test_exact_fit_is_feasible(self):
        bank = {("A", EASY): 2, ("A", HARD): 1}
        r = check_feasibility(bank, {"A": 3}, {EASY: 2, MOD: 0, HARD: 1}, 3)
        self.assertTrue(r.feasible)
        self.assertEqual(r.allocation[("A", EASY)], 2)


class AgainstBruteForceTests(unittest.TestCase):
    """Compare with an independent check: for every subset of topics,
    need <= sum over difficulties of min(difficulty count, bank supply)."""

    @staticmethod
    def brute_force_feasible(bank, topics, diffs):
        names = list(topics)
        for size in range(1, len(names) + 1):
            for subset in combinations(names, size):
                need = sum(topics[t] for t in subset)
                supply = sum(min(diffs[d], sum(bank.get((t, d), 0) for t in subset))
                             for d in diffs)
                if need > supply:
                    return False
        return True

    def test_random_instances(self):
        rng = random.Random(2026)
        feasible_seen = infeasible_seen = 0
        for _ in range(400):
            names = ["A", "B", "C"]
            topics = {t: rng.randint(0, 4) for t in names}
            total = sum(topics.values())
            if total == 0:
                continue
            cuts = sorted(rng.randint(0, total) for _ in range(2))
            diffs = {EASY: cuts[0], MOD: cuts[1] - cuts[0], HARD: total - cuts[1]}
            bank = {(t, d): rng.randint(0, 4) for t in names for d in DIFFS}

            expected = self.brute_force_feasible(bank, topics, diffs)
            r = check_feasibility(bank, topics, diffs, total,
                                  rng=random.Random(rng.random()))
            self.assertEqual(r.feasible, expected, (bank, topics, diffs))
            if r.feasible:
                feasible_seen += 1
                assert_valid_allocation(self, r, bank, topics, diffs)
            else:
                infeasible_seen += 1
                self.assertTrue(r.problems)
        self.assertGreater(feasible_seen, 20)
        self.assertGreater(infeasible_seen, 20)


if __name__ == "__main__":
    unittest.main()