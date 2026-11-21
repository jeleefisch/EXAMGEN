"""Student copies: each student's exam paper with its own answer sheet as the LAST page.

One PDF per version. For every copy: paper pages, then one full-page answer sheet
with that copy's QR code. Sheet geometry still comes only from core/sheet_layout.py.
Fonts, styles and text escaping are shared with pdf.py, so a question prints the
same here as in the "Paper only" PDF. (The paper story is still similar to
pdf.build_exam_paper; merging them is a planned cleanup.)
"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer,
)

from core import sheet_layout as L

from .pdf import FONT, ExamDoc, VersionDoc, _draw_sheet, _fmt, _styles, _text


class _CopyState:
    """Shared by the flowables and the footer: which copy are we printing?"""
    serial = 0
    first_page = 1


class _StartCopy(Flowable):
    """Zero-size marker placed at the start of each copy."""

    def __init__(self, state, serial):
        super().__init__()
        self.state, self.serial = state, serial

    def wrap(self, avail_w, avail_h):
        return (0, 0)

    def draw(self):
        self.state.serial = self.serial
        self.state.first_page = self.canv.getPageNumber()


class _SheetPage(Flowable):
    """Fills the whole page and draws the answer sheet at absolute page coordinates."""

    def __init__(self, exam, version, serial, total):
        super().__init__()
        self.exam, self.version, self.serial, self.total = exam, version, serial, total

    def wrap(self, avail_w, avail_h):
        return (avail_w, avail_h - 0.5)

    def draw(self):
        c = self.canv
        ax, ay = c.absolutePosition(0, 0)
        c.saveState()
        c.translate(-ax, -ay)  # back to the page's bottom-left corner
        _draw_sheet(c, self.exam, self.version, self.serial, self.total)
        c.restoreState()


def build_student_copies(exam: ExamDoc, version: VersionDoc, copies: int) -> bytes:
    if copies < 1:
        raise ValueError("Need at least one copy.")
    if not 1 <= len(version.items) <= L.MAX_ITEMS:
        raise ValueError(f"The answer sheet supports 1 to {L.MAX_ITEMS} items.")

    state = _CopyState()
    st = _styles()

    def footer(c, d):
        c.saveState()
        c.setFont(FONT, 8)
        c.drawString(20 * mm, 10 * mm, f"Version {version.code}  |  Sheet {state.serial:03d}")
        c.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {c.getPageNumber() - state.first_page + 1}")
        c.restoreState()

    margin = 20 * mm
    paper = PageTemplate(
        id="paper", onPageEnd=footer,
        frames=[Frame(margin, 20 * mm, A4[0] - 2 * margin, A4[1] - 38 * mm, id="body")],
    )
    sheet = PageTemplate(
        id="sheet",
        frames=[Frame(0, 0, A4[0], A4[1], leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0, id="full")],
    )
    buf = BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[paper, sheet],
                          title=f"{exam.title} - Student copies {version.code}")

    total_pts = exam.points_per_question * len(version.items)
    story = []
    for serial in range(1, copies + 1):
        story.append(_StartCopy(state, serial))
        if exam.institution:
            story.append(Paragraph(_text(exam.institution), st["sub"]))
        story.append(Paragraph(_text(exam.title), st["title"]))
        if exam.subject:
            story.append(Paragraph(_text(exam.subject), st["sub"]))
        story.append(Paragraph(f"VERSION {_text(version.code)}", st["big"]))
        story.append(Paragraph(
            "Name: ____________________________ &nbsp;&nbsp; Date: ____________<br/>"
            "Student No.: ______________________<br/><br/>"
            "Write your answers on the <b>answer sheet on the last page</b> of this paper. "
            f"{len(version.items)} questions, {_fmt(exam.points_per_question)} point(s) each, "
            f"{_fmt(total_pts)} total.", st["body"]))
        story.append(Spacer(1, 6 * mm))
        for n, item in enumerate(version.items, start=1):
            block = [Paragraph(f"<b>{n}.</b> {_text(item.text)}", st["q"])]
            for ch in item.choices:
                block.append(Paragraph(f"{_text(ch.label)}. {_text(ch.text)}", st["c"]))
            story.append(KeepTogether(block))
        story.append(NextPageTemplate("sheet"))
        story.append(PageBreak())
        story.append(_SheetPage(exam, version, serial, copies))
        if serial < copies:
            story.append(NextPageTemplate("paper"))
            story.append(PageBreak())
    doc.build(story)
    return buf.getvalue()