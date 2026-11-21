"""PDF writers: exam paper, answer key, answer sheets.

These functions take plain dataclasses (no Django), so they can be tested alone.
apps/documents/loaders.py converts database rows into these dataclasses.
Answer-sheet positions come ONLY from core/sheet_layout.py.

Fonts: if static/fonts/DejaVuSans.ttf and DejaVuSans-Bold.ttf exist they are
embedded (full Latin + math symbols). Otherwise the built-in Helvetica is used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from core import sheet_layout as L

# ------------------------------------------------------------------- fonts
FONT_DIR = Path(__file__).resolve().parents[2] / "static" / "fonts"
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _register_fonts():
    """Switch to DejaVu Sans when both font files are present."""
    global FONT, FONT_BOLD
    regular = FONT_DIR / "DejaVuSans.ttf"
    bold = FONT_DIR / "DejaVuSans-Bold.ttf"
    if regular.is_file() and bold.is_file():
        pdfmetrics.registerFont(TTFont("DejaVuSans", str(regular)))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold)))
        pdfmetrics.registerFontFamily(
            "DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold",
            italic="DejaVuSans", boldItalic="DejaVuSans-Bold",
        )
        FONT, FONT_BOLD = "DejaVuSans", "DejaVuSans-Bold"


_register_fonts()


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


def _text(value):
    """Escape for ReportLab's mini-HTML, but keep line breaks."""
    return (
        escape(str(value))
        .replace("\r\n", "\n").replace("\r", "\n")
        .replace("\n", "<br/>")
    )


def _fit(text, font, size, max_width):
    """Shorten text with '...' so it is at most max_width points wide."""
    if pdfmetrics.stringWidth(text, font, size) <= max_width:
        return text
    while text and pdfmetrics.stringWidth(text + "...", font, size) > max_width:
        text = text[:-1]
    return text.rstrip() + "..."


def _styles():
    return {
        "title": ParagraphStyle("title", fontName=FONT_BOLD, fontSize=16,
                                leading=19, alignment=1, spaceAfter=2),
        "sub": ParagraphStyle("sub", fontName=FONT, fontSize=10,
                              leading=12, alignment=1),
        "big": ParagraphStyle("big", fontName=FONT_BOLD, fontSize=20,
                              leading=24, alignment=1, spaceBefore=6,
                              spaceAfter=6),
        "body": ParagraphStyle("body", fontName=FONT, fontSize=10, leading=14),
        "q": ParagraphStyle("q", fontName=FONT, fontSize=10.5, leading=14,
                            spaceBefore=8),
        "c": ParagraphStyle("c", fontName=FONT, fontSize=10.5, leading=14,
                            leftIndent=18),
        "h2": ParagraphStyle("h2", fontName=FONT_BOLD, fontSize=13,
                             leading=16, spaceBefore=6, spaceAfter=4),
    }


# ----------------------------------------------------------------- exam paper
def build_exam_paper(exam: ExamDoc, version: VersionDoc) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title=f"{exam.title} - Version {version.code}",
    )
    st = _styles()

    story = []
    if exam.institution:
        story.append(Paragraph(_text(exam.institution), st["sub"]))
    story.append(Paragraph(_text(exam.title), st["title"]))
    if exam.subject:
        story.append(Paragraph(_text(exam.subject), st["sub"]))
    story.append(Paragraph(f"VERSION {_text(version.code)}", st["big"]))
    total = exam.points_per_question * len(version.items)
    story.append(Paragraph(
        "Name: ____________________________ &nbsp;&nbsp; Date: ____________<br/>"
        "Student No.: ______________________<br/><br/>"
        f"Answer on the separate answer sheet. Check that its version code is "
        f"<b>{_text(version.code)}</b>. {len(version.items)} questions, "
        f"{_fmt(exam.points_per_question)} point(s) each, {_fmt(total)} total.",
        st["body"]))
    story.append(Spacer(1, 6 * mm))

    for n, item in enumerate(version.items, start=1):
        block = [Paragraph(f"<b>{n}.</b> {_text(item.text)}", st["q"])]
        for c in item.choices:
            block.append(Paragraph(f"{_text(c.label)}. {_text(c.text)}", st["c"]))
        story.append(KeepTogether(block))

    def footer(c, d):
        c.saveState()
        c.setFont(FONT, 8)
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
    st = _styles()
    story = [
        Paragraph(f"{_text(exam.title)} - ANSWER KEY", st["title"]),
        Paragraph("<b>CONFIDENTIAL: faculty only.</b> Do not distribute.", st["body"]),
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
            ("FONTNAME", (0, 0), (-1, -1), FONT),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(KeepTogether([
            Paragraph(f"Version {_text(v.code)}", st["h2"]), table, Spacer(1, 5 * mm),
        ]))
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


def _draw_sheet(c, exam, version, serial, n_total, show_total=True):
    n = len(version.items)
    c.setFillColor(colors.black)
    for m in L.markers():
        c.rect(m.x, m.y, m.w, m.h, fill=1, stroke=0)

    left = 70
    top = L.PAGE_H - 62
    qr_left = L.qr_box().x
    c.setFont(FONT_BOLD, 14)
    c.drawString(left, top, "ANSWER SHEET")
    c.setFont(FONT, 10)
    c.drawString(left, top - 16, _fit(exam.title, FONT, 10, qr_left - left - 12))
    c.setFont(FONT_BOLD, 16)
    c.drawString(left, top - 40, f"VERSION {version.code}")
    c.setFont(FONT, 9)
    label = (f"Sheet {serial:03d} of {n_total:03d}" if show_total
             else f"Sheet {serial:03d}")
    c.drawString(left, top - 56, label)
    c.setFont(FONT, 10)
    c.drawString(left, top - 88, "Name: ______________________________")
    c.drawString(left, top - 108, "Student ID: ________________________")
    c.setFont(FONT, 8)
    c.drawString(left, top - 128, "Use a dark pen or pencil. Fill the bubble completely.")
    c.drawString(left, top - 139, "To change an answer, erase fully. Print at 100% (Actual size).")

    _draw_qr(c, L.encode_payload(version.code, serial), L.qr_box())

    c.setFont(FONT_BOLD, 8)
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
        c.setFont(FONT, 9)
        c.drawRightString(L.COLUMN_X[col] + 25, cy - 3, f"{item_no}.")
        for ch in range(L.choices_for(item.qtype)):
            b = L.bubble(item_no, ch)
            c.setFillColor(colors.white)
            c.circle(b.cx, b.cy, b.r, stroke=1, fill=1)
            c.setFillColor(colors.Color(0.55, 0.55, 0.55))
            c.setFont(FONT, 6)
            c.drawCentredString(b.cx, b.cy - 2, b.label)


def build_answer_sheets(exam: ExamDoc, version: VersionDoc, copies: int,
                        start_serial: int = 1) -> bytes:
    """One page per copy. Use start_serial to continue numbering on a reprint,
    so no two printed sheets of a version share a serial number."""
    if not 1 <= len(version.items) <= L.MAX_ITEMS:
        raise ValueError(f"The answer sheet supports 1 to {L.MAX_ITEMS} items.")
    if copies < 1:
        raise ValueError("At least one answer sheet is required.")
    if start_serial < 1:
        raise ValueError("Serial numbers start at 1.")
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"{exam.title} - Answer sheets {version.code}")
    for offset in range(copies):
        _draw_sheet(c, exam, version, start_serial + offset, copies,
                    show_total=(start_serial == 1))
        c.showPage()
    c.save()
    return buf.getvalue()