"""End-to-end check: simulated students -> synthetic photos -> upload -> read -> grade.

All figures printed here are DIGITAL/SYNTHETIC (rendered sheets with simulated
camera effects). They are not measurements of printed, hand-marked paper.
"""
import random
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.exams.models import VersionQuestion
from apps.omr.models import SheetScan
from apps.omr.tests import add_version, make_exam, photo_file

from .models import GradeResult

TMP = tempfile.mkdtemp()
LETTERS = "ABCD"
STUDENTS_PER_VERSION = 4
P_CORRECT, P_WRONG = 0.60, 0.25          # the rest are left blank

VERSIONS = [
    ("AC-A", 1, ["MC", "MC", "TF", "MC", "MC", "TF", "MC", "MC", "MC", "MC"]),
    ("AC-B", 2, ["TF", "MC", "MC", "MC", "TF", "MC", "MC", "MC", "TF", "MC"]),
    ("AC-C", 3, ["MC", "TF", "MC", "MC", "MC", "MC", "TF", "MC", "MC", "TF"]),
]


@override_settings(MEDIA_ROOT=TMP)
class GradingAccuracyTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def test_simulated_students_are_read_and_graded_correctly(self):
        rng = random.Random(2026)
        user = get_user_model().objects.create_user("acc", password="x")
        self.client.force_login(user)
        exam = make_exam(user)

        # Versions with varied answer keys (add_version makes every key "A").
        keys, types_of = {}, {}
        for code, seq, types in VERSIONS:
            version = add_version(exam, code, seq, types)
            types_of[code] = types
            keys[code] = {}
            for q in VersionQuestion.objects.filter(version=version):
                n = 2 if q.qtype == "TF" else 4
                q.correct_label = LETTERS[rng.randrange(n)]
                q.save(update_fields=["correct_label"])
                keys[code][q.position] = q.correct_label

        # Simulated students: ground truth is decided here, before any image exists.
        truth = {}       # (code, serial) -> {item: answer or "-"}
        expected = {}    # (code, serial) -> expected score
        upload_url = reverse("omr:upload", args=[exam.pk])
        photo_seed = 100
        for code, _seq, types in VERSIONS:
            for serial in range(1, STUDENTS_PER_VERSION + 1):
                answers, marks = {}, []
                for item, t in enumerate(types, start=1):
                    n = 2 if t == "TF" else 4
                    key = keys[code][item]
                    r = rng.random()
                    if r < P_CORRECT:
                        ans = key
                    elif r < P_CORRECT + P_WRONG:
                        ans = rng.choice([c for c in LETTERS[:n] if c != key])
                    else:
                        ans = "-"
                    answers[item] = ans
                    if ans != "-":
                        marks.append((item, ans, round(rng.uniform(0.75, 0.95), 2)))
                truth[(code, serial)] = answers
                expected[(code, serial)] = sum(1 for i, a in answers.items() if a == keys[code][i])
                photo_seed += 1
                self.client.post(upload_url, {
                    "photos": photo_file(code, serial, types, marks, seed=photo_seed)})

        total_sheets = len(VERSIONS) * STUDENTS_PER_VERSION
        scans = list(SheetScan.objects.filter(exam=exam).prefetch_related("items"))
        self.assertEqual(len(scans), total_sheets)

        # 1. Every sheet was identified (version + serial) and matches a simulated student.
        for s in scans:
            self.assertEqual(s.status, SheetScan.Status.READ, s.error)
            self.assertIn((s.version.code, s.serial), truth)

        # 2. Item level: a wrong answer is only acceptable if it was flagged for review.
        items_total = auto_correct = flagged = 0
        silent_errors = []
        ready_before = 0
        for s in scans:
            key = (s.version.code, s.serial)
            if s.is_ready:
                ready_before += 1
            for it in s.items.all():
                items_total += 1
                want = truth[key][it.item]
                if it.final == want:
                    auto_correct += 1
                elif it.needs_review:
                    flagged += 1
                else:
                    silent_errors.append((key, it.item, want, it.final))

        # 3. Grading: every graded score must equal the score computed from ground truth.
        self.client.post(reverse("grading:results", args=[exam.pk]), {"action": "grade_all"})
        grades = list(GradeResult.objects.filter(scan__exam=exam).select_related("scan__version"))
        score_mismatches = [
            ((g.scan.version.code, g.scan.serial), g.score,
             expected[(g.scan.version.code, g.scan.serial)])
            for g in grades
            if g.score != expected[(g.scan.version.code, g.scan.serial)]]

        print("\n--- Grading accuracy (DIGITAL/SYNTHETIC, not printed paper) ---")
        print(f"Sheets: {total_sheets} | identified: {total_sheets} | graded: {len(grades)}")
        print(f"Items: {items_total} | read correctly without review: {auto_correct} "
              f"({100 * auto_correct / items_total:.1f}%) | flagged for review: {flagged} "
              f"| silent errors: {len(silent_errors)}")
        print(f"Graded sheets with wrong score: {len(score_mismatches)}")

        self.assertEqual(silent_errors, [])
        self.assertEqual(len(grades), ready_before)
        self.assertEqual(score_mismatches, [])