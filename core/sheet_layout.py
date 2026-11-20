"""Answer-sheet geometry, shared by the PDF writer and (later) the OMR reader.

Pure Python, no Django. Units are PostScript points (1/72 inch) on an A4 page,
origin at the BOTTOM-LEFT (the PDF convention). Items are numbered from 1,
choices from 0 (0 = A). Layout: 25 rows per column, up to 2 columns (50 items).
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass

PAGE_W, PAGE_H = 595.2756, 841.8898  # A4
MAX_ITEMS = 50
MAX_CHOICES = 4
ROWS_PER_COLUMN = 25

MARKER_SIZE = 20.0
MARKER_INSET = 28.0  # page edge to marker edge

QR_SIZE = 90.0

GRID_TOP = PAGE_H - 240.0
ROW_PITCH = 22.0
COLUMN_X = (70.0, 320.0)  # left edge of each column block
BUBBLE_X0 = 45.0          # first bubble centre, measured from the column edge
CHOICE_PITCH = 30.0
BUBBLE_R = 7.0

LABELS = "ABCD"


@dataclass(frozen=True)
class Rect:
    x: float  # lower-left corner
    y: float
    w: float
    h: float

    def intersects(self, other: "Rect", pad: float = 0.0) -> bool:
        return not (
            self.x + self.w + pad <= other.x
            or other.x + other.w + pad <= self.x
            or self.y + self.h + pad <= other.y
            or other.y + other.h + pad <= self.y
        )


@dataclass(frozen=True)
class Bubble:
    item: int
    choice: int
    label: str
    cx: float
    cy: float
    r: float

    @property
    def rect(self) -> Rect:
        return Rect(self.cx - self.r, self.cy - self.r, 2 * self.r, 2 * self.r)


def choices_for(qtype: str) -> int:
    """Bubbles per item: MC has 4 (A-D), True/False has 2 (A=True, B=False)."""
    return 2 if qtype == "TF" else 4


def num_columns(n_items: int) -> int:
    _check_items(n_items)
    return 1 if n_items <= ROWS_PER_COLUMN else 2


def _check_items(n_items: int) -> None:
    if not 1 <= n_items <= MAX_ITEMS:
        raise ValueError(f"Items must be between 1 and {MAX_ITEMS}, got {n_items}.")


def column_and_row(item: int) -> tuple[int, int]:
    if not 1 <= item <= MAX_ITEMS:
        raise ValueError(f"Item must be between 1 and {MAX_ITEMS}, got {item}.")
    return (item - 1) // ROWS_PER_COLUMN, (item - 1) % ROWS_PER_COLUMN


def row_center_y(row: int) -> float:
    return GRID_TOP - ROW_PITCH / 2 - row * ROW_PITCH


def bubble(item: int, choice: int) -> Bubble:
    if not 0 <= choice < MAX_CHOICES:
        raise ValueError(f"Choice must be 0..{MAX_CHOICES - 1}, got {choice}.")
    col, row = column_and_row(item)
    cx = COLUMN_X[col] + BUBBLE_X0 + choice * CHOICE_PITCH
    return Bubble(item, choice, LABELS[choice], cx, row_center_y(row), BUBBLE_R)


def all_bubbles(choices_per_item: list[int]) -> list[Bubble]:
    """Every bubble for a sheet. choices_per_item[i] is the count for item i+1."""
    _check_items(len(choices_per_item))
    return [
        bubble(i + 1, c)
        for i, n in enumerate(choices_per_item)
        for c in range(n)
    ]


def markers() -> list[Rect]:
    """Four registration squares: BL, BR, TL, TR."""
    lo = MARKER_INSET
    hi_x = PAGE_W - MARKER_INSET - MARKER_SIZE
    hi_y = PAGE_H - MARKER_INSET - MARKER_SIZE
    return [Rect(x, y, MARKER_SIZE, MARKER_SIZE) for x, y in ((lo, lo), (hi_x, lo), (lo, hi_y), (hi_x, hi_y))]


def qr_box() -> Rect:
    return Rect(PAGE_W - 60.0 - QR_SIZE, PAGE_H - 70.0 - QR_SIZE, QR_SIZE, QR_SIZE)


# --- QR payload: "EG1|<version code>|<sheet serial>|<check>" ----------------
PAYLOAD_PREFIX = "EG1"


def _check(body: str) -> str:
    return format(zlib.crc32(body.encode("utf-8")) & 0xFFFF, "04X")


def encode_payload(version_code: str, serial: int) -> str:
    if "|" in version_code or not version_code:
        raise ValueError("Bad version code.")
    if serial < 1:
        raise ValueError("Serial starts at 1.")
    body = f"{PAYLOAD_PREFIX}|{version_code}|{serial}"
    return f"{body}|{_check(body)}"


def decode_payload(text: str):
    """Return (version_code, serial), or None if damaged or not ours."""
    parts = (text or "").split("|")
    if len(parts) != 4 or parts[0] != PAYLOAD_PREFIX or not parts[2].isdigit():
        return None
    body = "|".join(parts[:3])
    if parts[3] != _check(body):
        return None
    return parts[1], int(parts[2])