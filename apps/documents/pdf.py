"""PDF writers: exam paper, answer key, answer sheets.

These functions take plain dataclasses (no Django), so they can be tested alone.
apps/documents/loaders.py converts database rows into these dataclasses.
Answer-sheet positions come ONLY from core/sheet_layout.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from core import sheet_layout as L


@dataclass
class ChoiceDoc:
    label: str
    text: str


@dataclass
class ItemDoc:
    text: str
    qtype: str
    correct_label: str
    choices: list = field(default_factory=list)


@dataclass
class VersionDoc:
    code: str
    items: list = field(default_factory=list)


@dataclass
class ExamDoc:
    title: str
    subject: str = ""
    institution: str = ""
    points_per_question: float = 1


def _fmt(n):
    return f"{n:g}"


# ----------------------------------------------------------------- exam paper
def build_exam_paper(exam: ExamDoc, version: VersionDoc) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title=f"{exam.title} - Version {version.code}",
    )
    base = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=base["Title"], fontSize=16, spaceAfter=2)
    sub = ParagraphStyle("s", parent=base["Normal"], alignment=1, fontSize=10)
    big = ParagraphStyle("v", parent=base["Title"], fontSize=20, spaceBefore=6, spaceAfter=6)
    qst = ParagraphStyle("q", parent=base["Normal"], fontSize=10.5, leading=14, spaceBefore=8)
    cst = ParagraphStyle("c", parent=base["Normal"], fontSize=10.5, leading=14, leftIndent=18)

    story = []
    if exam.institution:
        story.append(Paragraph(escape(exam.institution), sub))
    story.append(Paragraph(escape(exam.title), title))
    if exam.subject:
        story.append(Paragraph(escape(exam.subject), sub))
    story.append(Paragraph(f"VERSION {escape(version.code)}", big))
    total = exam.points_per_question * len(version.items)
    story.append(Paragraph(
        f"Name: ____________________________ &nbsp;&nbsp; Date: ____________<br/><br/>"
        f"Answer on the separate answer sheet. Check that its version code is "
        f"<b>{escape(version.code)}</b>. {len(version.items)} questions, "
        f"{_fmt(exam.points_per_question)} point(s) each, {_fmt(total)} total.", base["Normal"]))
    story.append(Spacer(1, 6 * mm))

    for n, item in enumerate(version.items, start=1):
        block = [Paragraph(f"<b>{n}.</b> {escape(item.text)}", qst)]
        for c in item.choices:
            block.append(Paragraph(f"{escape(c.label)}. {escape(c.text)}", cst))
        story.append(KeepTogether(block))

    def footer(c, d):
        c.saveState()
        c.setFont("Helvetica", 8)
        c.drawString(20 * mm, 10 * mm, f"Version {version.code}")
        c.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {d.page}")
        c.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ----------------------------------------------------------------- answer key
def build_answer_key(exam: ExamDoc, versions: list) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"{exam.title} - Answer key")
    base = getSampleStyleSheet()
    story = [
        Paragraph(f"{escape(exam.title)} - ANSWER KEY", base["Title"]),
        Paragraph("<b>CONFIDENTIAL: faculty only.</b> Do not distribute.", base["Normal"]),
        Spacer(1, 5 * mm),
    ]
    per_row = 10
    for v in versions:
        cells = [f"{n}-{it.correct_label}" for n, it in enumerate(v.items, start=1)]
        rows = [cells[i:i + per_row] for i in range(0, len(cells), per_row)]
        width = (A4[0] - 40 * mm) / per_row
        table = Table(rows, colWidths=[width] * per_row)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(KeepTogether([Paragraph(f"Version {escape(v.code)}", base["Heading2"]), table, Spacer(1, 5 * mm)]))
    doc.build(story)
    return buf.getvalue()


# ------------------------------------------------------------- answer sheets
def _draw_qr(c, payload, box):
    widget = qr.QrCodeWidget(payload, barLevel="M")
    x0, y0, x1, y1 = widget.getBounds()
    w, h = x1 - x0, y1 - y0
    d = Drawing(box.w, box.h, transform=[box.w / w, 0, 0, box.h / h, 0, 0])
    d.add(widget)
    renderPDF.draw(d, c, box.x, box.y)


def _draw_sheet(c, exam, version, serial, n_total):
    n = len(version.items)
    c.setFillColor(colors.black)
    for m in L.markers():
        c.rect(m.x, m.y, m.w, m.h, fill=1, stroke=0)

    left = 70
    top = L.PAGE_H - 62
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left, top, "ANSWER SHEET")
    c.setFont("Helvetica", 10)
    c.drawString(left, top - 16, exam.title[:70])
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, top - 40, f"VERSION {version.code}")
    c.setFont("Helvetica", 9)
    c.drawString(left, top - 56, f"Sheet {serial:03d} of {n_total:03d}")
    c.setFont("Helvetica", 10)
    c.drawString(left, top - 88, "Name: ______________________________")
    c.drawString(left, top - 108, "Student ID: ________________________")
    c.setFont("Helvetica", 8)
    c.drawString(left, top - 128, "Use a dark pen or pencil. Fill the bubble completely.")
    c.drawString(left, top - 139, "To change an answer, erase fully. Print at 100% (Actual size).")

    _draw_qr(c, L.encode_payload(version.code, serial), L.qr_box())

    # column headings A B C D
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.black)
    for col in range(L.num_columns(n)):
        for ch in range(L.MAX_CHOICES):
            x = L.COLUMN_X[col] + L.BUBBLE_X0 + ch * L.CHOICE_PITCH
            c.drawCentredString(x, L.GRID_TOP + 6, L.LABELS[ch])

    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    for item_no, item in enumerate(version.items, start=1):
        col, row = L.column_and_row(item_no)
        cy = L.row_center_y(row)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9)
        c.drawRightString(L.COLUMN_X[col] + 25, cy - 3, f"{item_no}.")
        for ch in range(L.choices_for(item.qtype)):
            b = L.bubble(item_no, ch)
            c.setFillColor(colors.white)
            c.circle(b.cx, b.cy, b.r, stroke=1, fill=1)
            c.setFillColor(colors.Color(0.55, 0.55, 0.55))
            c.setFont("Helvetica", 6)
            c.drawCentredString(b.cx, b.cy - 2, b.label)


def build_answer_sheets(exam: ExamDoc, version: VersionDoc, copies: int) -> bytes:
    if not 1 <= len(version.items) <= L.MAX_ITEMS:
        raise ValueError(f"The answer sheet supports 1 to {L.MAX_ITEMS} items.")
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"{exam.title} - Answer sheets {version.code}")
    for serial in range(1, copies + 1):
        _draw_sheet(c, exam, version, serial, copies)
        c.showPage()
    c.save()
    return buf.getvalue()