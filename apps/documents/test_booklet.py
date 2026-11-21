import unittest

from apps.documents import booklet
from apps.documents.test_pdf import EXAM, make_version, pages


class StudentCopiesTests(unittest.TestCase):
    def test_is_a_pdf(self):
        data = booklet.build_student_copies(EXAM, make_version(), 1)
        self.assertTrue(data.startswith(b"%PDF"))

    def test_every_copy_is_paper_pages_plus_one_sheet_page(self):
        one = pages(booklet.build_student_copies(EXAM, make_version(), 1))
        self.assertGreaterEqual(one, 2)  # at least one paper page + the sheet
        for copies in (2, 5):
            self.assertEqual(pages(booklet.build_student_copies(EXAM, make_version(), copies)),
                             copies * one)

    def test_long_exam_with_full_sheet(self):
        data = booklet.build_student_copies(EXAM, make_version(n=50), 2)
        self.assertEqual(pages(data) % 2, 0)

    def test_special_characters_do_not_break_it(self):
        v = make_version()
        v.items[0].text = "<<&&>> <i>broken"
        self.assertTrue(booklet.build_student_copies(EXAM, v, 1).startswith(b"%PDF"))

    def test_rejects_bad_inputs(self):
        with self.assertRaises(ValueError):
            booklet.build_student_copies(EXAM, make_version(), 0)
        with self.assertRaises(ValueError):
            booklet.build_student_copies(EXAM, make_version(n=51), 1)