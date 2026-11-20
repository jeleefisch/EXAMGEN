import re
import unittest

from apps.documents import pdf


def pages(data: bytes) -> int:
    return len(re.findall(rb"/Type /Page[^s]", data))


def make_version(code="E1-A", n=12):
    items = []
    for i in range(1, n + 1):
        tf = i % 5 == 0
        labels = "AB" if tf else "ABCD"
        items.append(pdf.ItemDoc(
            text=f"Is 3 < 5 & 2 > 1 <b>unclosed? ({i})", qtype="TF" if tf else "MC",
            correct_label="A", choices=[pdf.ChoiceDoc(l, f"x & <y> {l}") for l in labels]))
    return pdf.VersionDoc(code, items)


EXAM = pdf.ExamDoc("Midterm <1>", "Math & Logic", "Some University", 2)


class PdfWriterTests(unittest.TestCase):
    def test_paper_is_a_pdf_and_survives_special_characters(self):
        data = pdf.build_exam_paper(EXAM, make_version())
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreaterEqual(pages(data), 1)

    def test_long_paper_spans_several_pages(self):
        self.assertGreater(pages(pdf.build_exam_paper(EXAM, make_version(n=50))), 1)

    def test_key_is_a_pdf_for_several_versions(self):
        data = pdf.build_answer_key(EXAM, [make_version("E1-A"), make_version("E1-B")])
        self.assertTrue(data.startswith(b"%PDF"))

    def test_one_sheet_page_per_copy(self):
        for copies in (1, 3, 10):
            data = pdf.build_answer_sheets(EXAM, make_version(), copies)
            self.assertTrue(data.startswith(b"%PDF"))
            self.assertEqual(pages(data), copies)

    def test_full_50_item_sheet_builds(self):
        self.assertEqual(pages(pdf.build_answer_sheets(EXAM, make_version(n=50), 1)), 1)

    def test_sheet_rejects_zero_or_too_many_items(self):
        with self.assertRaises(ValueError):
            pdf.build_answer_sheets(EXAM, make_version(n=51), 1)
        with self.assertRaises(ValueError):
            pdf.build_answer_sheets(EXAM, pdf.VersionDoc("E1-A", []), 1)