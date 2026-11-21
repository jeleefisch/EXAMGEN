from django.test import SimpleTestCase

from core.benchmark import format_report, run_benchmark


class BenchmarkTests(SimpleTestCase):
    def run_small(self, seed=1):
        return run_benchmark(sheets=2, seed=seed, conditions=["mild"], items_range=(10, 12))

    def test_counts_are_consistent(self):
        c = self.run_small()["conditions"]["mild"]
        self.assertEqual(c["sheets"], 2)
        self.assertEqual(c["sheets"], c["read"] + c["unreadable"] + c["crashed"])
        self.assertEqual(c["items"], c["correct"] + c["flagged"] + c["confident_wrong"])
        self.assertEqual(c["crashed"], 0)
        self.assertGreater(c["items"], 0)

    def test_same_seed_gives_same_result(self):
        self.assertEqual(self.run_small(5)["total"], self.run_small(5)["total"])

    def test_report_is_labelled_synthetic_in_both_formats(self):
        result = self.run_small()
        text = format_report(result)
        md = format_report(result, markdown=True)
        self.assertIn("SYNTHETIC", text)
        self.assertIn("SYNTHETIC", md)
        self.assertIn("| condition |", md)
        self.assertIn("TOTAL", text)

    def test_unknown_condition_is_rejected(self):
        with self.assertRaises(ValueError):
            run_benchmark(sheets=1, conditions=["nope"])