"""Reading real (text-layer) PDFs page by page for inspection and rule-based checks.

Unlike ``layout.py`` (tuned to the synthetic documents) this keeps pages
separate, since annotations and findings reference 1-based pages, and repairs
what real Word-exported tables look like in pdfplumber:

* header words wrapped inside a cell without a hyphen: ``Этажнос\\nть``,
  ``Общая\\nплощад\\nь`` → ``Этажность``, ``Общая площадь``;
* a word split across two adjacent header cells (``Этажнос`` | ``ть``).

Both repairs are heuristics (see ``_is_fragment``): the second part must be a
lowercase 1–3 letter token that is not a preposition or a unit, and the first
part must end with a letter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

BBox = tuple[float, float, float, float]  # x0, top, x1, bottom (PDF points, origin top-left)

_FRAGMENT_RE = re.compile(r"[а-яёәғқңөұүһіa-z]{1,3}")
# short lowercase tokens that are real words, never word tails
_NOT_FRAGMENTS = frozenset(
    "в и с к о у а я на по до от за из со во не ни для при под над без или же ли бы то "
    "шт эт мм см км кг га тн т г л ед изм".split()
)


def norm_ws(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _is_fragment(prev: str, token: str) -> bool:
    return bool(prev) and prev[-1].isalpha() and bool(_FRAGMENT_RE.fullmatch(token)) and token not in _NOT_FRAGMENTS


def glue_wrapped(cell: str | None) -> str:
    """Join the lines of a table cell, gluing word tails wrapped without a hyphen."""
    lines = [ln.strip() for ln in (cell or "").split("\n") if ln.strip()]
    if not lines:
        return ""
    out = lines[0]
    for nxt in lines[1:]:
        first, _, rest = nxt.partition(" ")
        if out.endswith("-") and nxt[0].islower():
            out = out[:-1] + nxt
        elif _is_fragment(out, first):
            out = out + first + (" " + rest if rest else "")
        else:
            out = out + " " + nxt
    return norm_ws(out)


def merge_split_header(row: list[str]) -> list[str]:
    """Repair a word split across adjacent header cells; both cells get the full label."""
    row = list(row)
    for i in range(len(row) - 1):
        if row[i] and _is_fragment(row[i], row[i + 1]):
            row[i] = row[i + 1] = row[i] + row[i + 1]
    return row


@dataclass
class TextLine:
    text: str
    top: float


@dataclass
class PageTable:
    rows: list[list[str]]  # cells after glue_wrapped, None -> ""
    bbox: BBox
    header: list[str] = field(default_factory=list)  # first row after merge_split_header

    @property
    def top(self) -> float:
        return self.bbox[1]


@dataclass
class Page:
    number: int  # 1-based
    text: str  # pdfplumber extract_text(), as is
    lines: list[TextLine]
    tables: list[PageTable]

    def lines_above(self, top: float) -> list[TextLine]:
        return [ln for ln in self.lines if ln.top < top]


def load_pages(path: str | Path) -> list[Page]:
    pages = []
    with pdfplumber.open(path) as pdf:
        for no, p in enumerate(pdf.pages, start=1):
            tables = []
            for t in p.find_tables():
                rows = [[glue_wrapped(c) for c in row] for row in t.extract()]
                if rows:
                    tables.append(PageTable(rows, tuple(t.bbox), merge_split_header(rows[0])))
            lines = [TextLine(norm_ws(ln["text"]), float(ln["top"])) for ln in p.extract_text_lines()]
            pages.append(Page(no, p.extract_text() or "", lines, tables))
    return pages
