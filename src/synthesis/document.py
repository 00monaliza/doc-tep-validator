"""Language-agnostic intermediate representation of a generated document.

Templates build a `Document`; renderers (PDF/DOCX) consume it. Every TEP value
that a template writes is registered as an anchor, so ground truth can point to
the exact table cell or sentence where the value appears.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BlockKind = Literal["title", "heading", "para", "table"]


@dataclass
class Block:
    id: str
    kind: BlockKind
    text: str = ""
    header: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    col_widths: list[float] = field(default_factory=list)  # relative
    bold_rows: set[int] = field(default_factory=set)  # subtotal / group rows


@dataclass
class Anchor:
    block_id: str
    text: str  # exact string as rendered
    row: int | None = None  # 0-based data row index (header excluded)
    col: int | None = None

    def to_json(self) -> dict:
        d = {"block_id": self.block_id, "text": self.text}
        if self.row is not None:
            d |= {"row": self.row, "col": self.col}
        return d


@dataclass
class TableRows:
    """Accumulates table rows and remembers which cell holds which TEP field."""

    rows: list[list[str]] = field(default_factory=list)
    cells: dict[str, tuple[int, int]] = field(default_factory=dict)
    bold: set[int] = field(default_factory=set)

    def add(self, row: list[str], fields: dict[str, int] | None = None, bold: bool = False) -> None:
        """`fields` maps TEP field -> column index of its value in `row`."""
        idx = len(self.rows)
        self.rows.append(row)
        for fld, col in (fields or {}).items():
            self.cells[fld] = (idx, col)
        if bold:
            self.bold.add(idx)

    @property
    def next_no(self) -> str:
        """Running '№ п/п' that skips bold group/subtotal rows."""
        return str(len(self.rows) - len(self.bold) + 1)


@dataclass
class Document:
    section: str
    lang: str
    code: str  # e.g. "0412-2026-ПЗ"
    title: str
    blocks: list[Block] = field(default_factory=list)
    anchors: dict[str, list[Anchor]] = field(default_factory=dict)

    def _id(self, prefix: str) -> str:
        return f"{prefix}{sum(b.id.startswith(prefix) for b in self.blocks) + 1}"

    def title_block(self, text: str) -> None:
        self.blocks.append(Block(self._id("t"), "title", text=text))

    def heading(self, text: str) -> None:
        self.blocks.append(Block(self._id("h"), "heading", text=text))

    def para(self, text: str, mentions: dict[str, str] | None = None) -> str:
        """Add a paragraph; `mentions` maps TEP field -> substring holding its value."""
        block = Block(self._id("p"), "para", text=text)
        self.blocks.append(block)
        for fld, value_text in (mentions or {}).items():
            assert value_text in text, f"{value_text!r} not in paragraph"
            self.anchors.setdefault(fld, []).append(Anchor(block.id, value_text))
        return block.id

    def table(
        self,
        header: list[str],
        rows: list[list[str]],
        col_widths: list[float],
        cells: dict[str, tuple[int, int]] | None = None,
        bold_rows: set[int] | None = None,
        block_id: str | None = None,
    ) -> str:
        """Add a table; `cells` maps TEP field -> (row, col) of the value cell."""
        block = Block(block_id or self._id("tbl"), "table", header=header, rows=rows,
                      col_widths=col_widths, bold_rows=bold_rows or set())
        self.blocks.append(block)
        for fld, (r, c) in (cells or {}).items():
            self.anchors.setdefault(fld, []).append(Anchor(block.id, rows[r][c], r, c))
        return block.id

    def add_rows(self, header: list[str], t: TableRows, col_widths: list[float], block_id: str) -> str:
        return self.table(header, t.rows, col_widths, t.cells, t.bold, block_id)
