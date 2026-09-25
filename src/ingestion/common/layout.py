"""Reading-order layout of a text-layer PDF: text lines and tables, with coordinates.

Tables come from pdfplumber (ruled tables are recovered cell-exact); a table that
continues on the next page with a repeated header is merged into one. Text
outside tables is kept as lines with bounding boxes so any match can be
highlighted in the viewer. Coordinates are PDF points, origin top-left.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

BBox = tuple[float, float, float, float]  # x0, top, x1, bottom


def norm_ws(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


@dataclass
class Cell:
    text: str  # whitespace-normalised
    page: int  # 1-based
    bbox: BBox | None


@dataclass
class Table:
    header: list[str]
    rows: list[list[Cell]]
    page: int  # first page
    context: str = ""  # text lines right above the table (heading / caption)

    def column(self, *patterns: str) -> int | None:
        """Index of the first header cell matching any regex (case-insensitive)."""
        for i, h in enumerate(self.header):
            if any(re.search(p, h, re.IGNORECASE) for p in patterns):
                return i
        return None


@dataclass
class Line:
    text: str
    page: int
    bbox: BBox | None  # None for DOCX and OCR lines


@dataclass
class Layout:
    path: str
    n_pages: int
    items: list[Line | Table] = field(default_factory=list)

    @property
    def lines(self) -> list[Line]:
        return [i for i in self.items if isinstance(i, Line)]

    @property
    def tables(self) -> list[Table]:
        return [i for i in self.items if isinstance(i, Table)]

    def text(self) -> str:
        return "\n".join(i.text for i in self.lines)

    def has_text(self) -> bool:
        return any(i.text.strip() for i in self.lines) or bool(self.tables)


def _lines_in(page, top: float, bottom: float, page_no: int) -> list[Line]:
    if bottom - top < 1:
        return []
    region = page.crop((0, top, page.width, bottom))
    return [Line(norm_ws(ln["text"]), page_no, (ln["x0"], ln["top"], ln["x1"], ln["bottom"]))
            for ln in region.extract_text_lines() if norm_ws(ln["text"])]


FURNITURE_MARGIN = 72.0  # pt (1 inch): running headers/footers live in these top/bottom bands


def parse_pdf(path: str | Path) -> Layout:
    layout = Layout(str(path), 0)
    last_table: Table | None = None
    since_table: list[Line] = []  # lines seen after the last table
    with pdfplumber.open(path) as pdf:
        layout.n_pages = len(pdf.pages)
        for page_no, page in enumerate(pdf.pages, start=1):
            def furniture(ln: Line, h: float = page.height) -> bool:
                return ln.bbox[3] < FURNITURE_MARGIN or ln.bbox[1] > h - FURNITURE_MARGIN

            cursor = 0.0
            for t in sorted(page.find_tables(), key=lambda t: t.bbox[1]):
                above = _lines_in(page, cursor, t.bbox[1], page_no)
                layout.items.extend(above)
                since_table.extend(above)
                texts = t.extract()
                cells = [[Cell(norm_ws(txt), page_no, cb) for txt, cb in zip(row_txt, row.cells, strict=False)]
                         for row_txt, row in zip(texts, t.rows, strict=False)]
                header = [c.text for c in cells[0]]
                if (last_table is not None and header == last_table.header
                        and all(furniture(ln) for ln in since_table)):
                    last_table.rows.extend(cells[1:])  # continuation with repeated header
                else:
                    context = " ".join(ln.text for ln in above if not furniture(ln))[-300:]
                    last_table = Table(header, cells[1:], page_no, context)
                    layout.items.append(last_table)
                since_table = []
                cursor = t.bbox[3]
            tail = _lines_in(page, cursor, page.height, page_no)
            layout.items.extend(tail)
            since_table.extend(tail)
    return layout


def parse_docx(path: str | Path) -> Layout:
    """DOCX body in order: paragraphs -> lines, tables -> tables (no pages / coordinates)."""
    import docx
    from docx.table import Table as DocxTable
    from docx.text.paragraph import Paragraph

    document = docx.Document(str(path))
    layout = Layout(str(path), 1)
    recent: list[str] = []
    for el in document.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = norm_ws(Paragraph(el, document).text)
            if text:
                layout.items.append(Line(text, 1, None))
                recent.append(text)
        elif tag == "tbl":
            rows = [[Cell(norm_ws(c.text), 1, None) for c in r.cells] for r in DocxTable(el, document).rows]
            if rows:
                layout.items.append(Table([c.text for c in rows[0]], rows[1:], 1, " ".join(recent[-2:])[-300:]))
            recent = []
    return layout
