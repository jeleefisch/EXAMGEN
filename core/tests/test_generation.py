import random
import unittest
from collections import Counter

from core.generation.entities import GeneratedVersion, Question
from core.generation.generator import (check_constraints, generate_versions,
                                       letter_code)
from core.generation.selection import select_questions
from core.generation.shuffle import choice_order, correct_label, fisher_yates

EASY, MOD, HARD = "Easy", "Moderate", "Difficult"
DIFFS = (EASY, MOD, HARD)
TOPICS = {"A": 5, "B": 7, "C": 8}
DIFF_REQ = {EASY: 6, MOD: 8, HARD: 6}


def make_bank(per_cell=8, topics=("A", "B", "C"), seed=1, tf_every=0):
    """Synthetic bank: per_cell questions for every topic/difficulty cell."""
    rng = random.Random(seed)
    bank, qid = [], 1
    for t in topics:
        for d in DIFFS:
            for _ in range(per_cell):
                if tf_every and qid % tf_every == 0:
                    bank.append(Question(qid, t, d, "TF", 2, rng.randrange(2)))
                else:
                    bank.append(Question(qid, t, d, "MC", 4, rng.randrange(4)))
                qid += 1
    return bank


def by_id(bank):
    return {q.id: q for q in bank}


class FisherYatesTests(unittest.TestCase):
    def test_keeps_the_same_elements(self):
        out = fisher_yates(range(10), random.Random(1))
        self.assertEqual(sorted(out), list(range(10)))

    def test_does_not_modify_input(self):
        original = [1, 2, 3, 4]
        fisher_yates(original, random.Random(1))
        self.assertEqual(original, [1, 2, 3, 4])

    def test_every_ordering_roughly_equally_likely(self):
        rng = random.Random(42)
        counts = Counter(tuple(fisher_yates("abc", rng)) for _ in range(6000))
        self.assertEqual(len(counts), 6)
        for n in counts.values():          # expected 1000 each
            self.assertTrue(800 < n < 1200, counts)


class ChoiceMappingTests(unittest.TestCase):
    def test_correct_label_follows_the_answer(self):
        rng = random.Random(5)
        for correct in range(4):
            for _ in range(50):
                order = choice_order(4, rng)
                label = correct_label(order, correct)
                self.assertEqual(order["ABCD".index(label)], correct)

    def test_disabled_keeps_original_order(self):
        order = choice_order(4, random.Random(1), enabled=False)
        self.assertEqual(order, (0, 1, 2, 3))
        self.assertEqual(correct_label(order, 2), "C")


class SelectionTests(unittest.TestCase):
    def test_prefers_least_used_questions(self):
        pool = [Question(i, "A", EASY, "MC", 4, 0) for i in range(1, 7)]
        usage = {1: 2, 2: 2, 3: 1}       # 4, 5, 6 are unused
        chosen = select_questions({("A", EASY): pool}, {("A", EASY): 3},
                                  usage, random.Random(0))
        self.assertEqual({q.id for q in chosen}, {4, 5, 6})

    def test_rejects_an_impossible_cell(self):
        pool = [Question(1, "A", EASY, "MC", 4, 0)]
        with self.assertRaises(ValueError):
            select_questions({("A", EASY): pool}, {("A", EASY): 2}, {},
                             random.Random(0))


class LetterCodeTests(unittest.TestCase):
    def test_sequence(self):
        self.assertEqual([letter_code(i) for i in (0, 1, 25, 26, 27, 51, 52)],
                         ["A", "B", "Z", "AA", "AB", "AZ", "BA"])


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.bank = make_bank()
        self.lookup = by_id(self.bank)

    def generate(self, versions=5, **kw):
        return generate_versions(self.bank, TOPICS, DIFF_REQ, 20, versions, **kw)

    def test_every_version_satisfies_all_constraints(self):
        report = self.generate(5, base_seed=1)
        self.assertTrue(report.feasible)
        self.assertEqual(report.success_count, 5)
        for v in report.versions:
            self.assertEqual(check_constraints(v, self.lookup, TOPICS,
                                               DIFF_REQ, 20), [])

    def test_constraint_satisfaction_rate_is_100_percent(self):
        total = ok = 0
        for seed in range(50):
            for v in self.generate(4, base_seed=seed).versions:
                total += 1
                ok += not check_constraints(v, self.lookup, TOPICS, DIFF_REQ, 20)
        self.assertEqual(ok, total)

    def test_codes_and_seeds_are_unique(self):
        report = self.generate(6, code_prefix="X-")
        codes = [v.code for v in report.versions]
        self.assertEqual(codes, ["X-A", "X-B", "X-C", "X-D", "X-E", "X-F"])
        self.assertEqual(len({v.seed for v in report.versions}), 6)

    def test_positions_run_from_one_to_total(self):
        v = self.generate(1).versions[0]
        self.assertEqual([i.position for i in v.items], list(range(1, 21)))

    def test_answer_key_matches_shuffled_choices(self):
        for v in self.generate(5, base_seed=3).versions:
            for item in v.items:
                q = self.lookup[item.question_id]
                slot = "ABCD".index(item.correct_label)
                self.assertEqual(item.choice_order[slot], q.correct_index)
                self.assertEqual(sorted(item.choice_order), [0, 1, 2, 3])

    def test_choices_not_shuffled_when_disabled(self):
        report = self.generate(2, shuffle_answer_choices=False)
        for v in report.versions:
            for item in v.items:
                q = self.lookup[item.question_id]
                self.assertEqual(item.choice_order, (0, 1, 2, 3))
                self.assertEqual(item.correct_label, "ABCD"[q.correct_index])

    def test_true_false_is_never_shuffled(self):
        self.bank = make_bank(tf_every=3)
        self.lookup = by_id(self.bank)
        report = self.generate(3, base_seed=9)
        seen_tf = 0
        for v in report.versions:
            self.assertEqual(check_constraints(v, self.lookup, TOPICS,
                                               DIFF_REQ, 20), [])
            for item in v.items:
                if self.lookup[item.question_id].qtype == "TF":
                    seen_tf += 1
                    self.assertEqual(item.choice_order, (0, 1))
        self.assertGreater(seen_tf, 0)

    def test_question_order_is_randomized_between_versions(self):
        report = self.generate(2, base_seed=4)
        a, b = report.versions
        self.assertNotEqual([i.question_id for i in a.items],
                            [i.question_id for i in b.items])

    def test_question_order_when_not_randomized_is_grouped(self):
        v = self.generate(1, shuffle_question_order=False).versions[0]
        topics = [i.topic for i in v.items]
        self.assertEqual(topics, sorted(topics))   # A..., B..., C...

    def test_same_seed_reproduces_everything(self):
        a = self.generate(4, base_seed=11)
        b = self.generate(4, base_seed=11)
        self.assertEqual([v.items for v in a.versions],
                         [v.items for v in b.versions])

    def test_different_seed_gives_different_versions(self):
        a = self.generate(1, base_seed=1).versions[0]
        b = self.generate(1, base_seed=2).versions[0]
        self.assertNotEqual(a.items, b.items)

    def test_two_versions_from_a_big_bank_never_share_questions(self):
        for seed in range(40):
            r = self.generate(2, base_seed=seed)
            self.assertEqual(r.overlaps[0].shared, 0, seed)

    def test_three_versions_from_a_big_bank_overlap_is_low(self):
        means = [self.generate(3, base_seed=s).summary["mean_jaccard"]
                 for s in range(40)]
        self.assertLess(sum(means) / len(means), 0.02)

    def test_report_contains_overlap_statistics_and_estimate(self):
        r = self.generate(3)
        self.assertEqual(len(r.overlaps), 3)
        self.assertEqual(r.summary["pairs"], 3)
        self.assertGreater(r.selection_estimate, 1_000_000)
        self.assertGreaterEqual(r.duration_ms, 0)


class HonestyTests(unittest.TestCase):
    def test_warns_when_the_bank_is_too_small_for_distinct_versions(self):
        bank = make_bank(per_cell=8)               # 72 usable questions
        r = generate_versions(bank, TOPICS, DIFF_REQ, 20, 5, base_seed=1)
        self.assertTrue(any("must repeat" in w for w in r.warnings))
        self.assertGreater(r.summary["max_jaccard"], 0)

    def test_no_such_warning_when_the_bank_is_big_enough(self):
        bank = make_bank(per_cell=8)
        r = generate_versions(bank, TOPICS, DIFF_REQ, 20, 3, base_seed=1)
        self.assertFalse(any("must repeat" in w for w in r.warnings))

    def test_identical_question_sets_are_reported(self):
        bank = make_bank(per_cell=1)               # 9 questions, exam needs all 9
        r = generate_versions(bank, {"A": 3, "B": 3, "C": 3},
                              {EASY: 3, MOD: 3, HARD: 3}, 9, 3, base_seed=1)
        self.assertEqual(r.summary["max_jaccard"], 1.0)
        self.assertTrue(any("exactly the same questions" in w
                            for w in r.warnings))

    def test_small_bank_that_still_allows_disjoint_versions(self):
        bank = make_bank(per_cell=2)               # 18 questions, 3 x 6 = 18
        r = generate_versions(bank, {"A": 2, "B": 2, "C": 2},
                              {EASY: 2, MOD: 2, HARD: 2}, 6, 3, base_seed=1)
        self.assertEqual(r.summary["max_jaccard"], 0.0)
        self.assertFalse(any("must repeat" in w for w in r.warnings))

    def test_similarity_limit_triggers_retries_and_warning(self):
        bank = make_bank(per_cell=8)
        r = generate_versions(bank, TOPICS, DIFF_REQ, 20, 5, base_seed=1,
                              max_similarity=0.0, max_attempts=4)
        self.assertEqual(r.success_count, 5)       # best effort, still delivered
        self.assertTrue(any(v.attempts == 4 for v in r.versions))
        self.assertTrue(any("similarity limit" in w for w in r.warnings))

    def test_achievable_similarity_limit_needs_no_retries(self):
        bank = make_bank(per_cell=8)
        r = generate_versions(bank, TOPICS, DIFF_REQ, 20, 2, base_seed=1,
                              max_similarity=0.5)
        self.assertTrue(all(v.attempts == 1 for v in r.versions))
        self.assertFalse(any("similarity limit" in w for w in r.warnings))


class RejectionTests(unittest.TestCase):
    def test_impossible_configuration_produces_no_versions(self):
        bank = make_bank(per_cell=1)               # only 9 questions
        r = generate_versions(bank, TOPICS, DIFF_REQ, 20, 3)
        self.assertFalse(r.feasible)
        self.assertEqual(r.versions, [])
        self.assertTrue(r.problems)

    def test_duplicate_question_ids_rejected(self):
        q = Question(1, "A", EASY, "MC", 4, 0)
        with self.assertRaises(ValueError):
            generate_versions([q, q], {"A": 1}, {EASY: 1}, 1, 1)

    def test_zero_versions_rejected(self):
        with self.assertRaises(ValueError):
            generate_versions(make_bank(), TOPICS, DIFF_REQ, 20, 0)

    def test_invalid_questions_rejected(self):
        with self.assertRaises(ValueError):
            Question(1, "A", EASY, "MC", 4, 4)       # correct_index too big
        with self.assertRaises(ValueError):
            Question(1, "A", EASY, "MC", 3, 0)       # MC needs 4 choices
        with self.assertRaises(ValueError):
            Question(1, "A", EASY, "ESSAY", 4, 0)    # unknown type


class VerifierCatchesBugsTests(unittest.TestCase):
    """The independent checker must actually detect broken versions."""

    def test_detects_wrong_answer_key(self):
        bank = make_bank()
        v = generate_versions(bank, TOPICS, DIFF_REQ, 20, 1).versions[0]
        item = v.items[0]
        wrong = "ABCD"[("ABCD".index(item.correct_label) + 1) % 4]
        broken = GeneratedVersion(v.code, v.seed, v.attempts,
                                  [item.__class__(item.position, item.question_id,
                                                  item.topic, item.difficulty,
                                                  item.choice_order, wrong)]
                                  + v.items[1:])
        problems = check_constraints(broken, by_id(bank), TOPICS, DIFF_REQ, 20)
        self.assertTrue(any("answer key" in p for p in problems))

    def test_detects_missing_and_duplicate_questions(self):
        bank = make_bank()
        v = generate_versions(bank, TOPICS, DIFF_REQ, 20, 1).versions[0]
        short = GeneratedVersion(v.code, v.seed, 1, v.items[:19])
        self.assertTrue(check_constraints(short, by_id(bank), TOPICS,
                                          DIFF_REQ, 20))
        dup = GeneratedVersion(v.code, v.seed, 1, v.items[:19] + [v.items[0]])
        self.assertTrue(any("more than once" in p for p in
                            check_constraints(dup, by_id(bank), TOPICS,
                                              DIFF_REQ, 20)))


if __name__ == "__main__":
    unittest.main()