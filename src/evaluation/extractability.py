"""How findable are the annotated TEP values in a real document?

For every value in ``annotation.tep[object][field]`` (a list means the document
states several values; each is looked up separately) we check whether, after
number normalization, it occurs

* in an extracted table, and if so whether under a header that names the field
  (``column_ok``) — the only case where a table extractor could get it right;
* only in the page text (sentences, or table rows pdfplumber did not detect);
* nowhere.

This is a measurement, not a pass/fail test. Small integers (floors, seismic
points, months) occur everywhere, so their hits are marked ``trivial``.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from src.evaluation.schema import RealAnnotation
from src.ingestion.common.numbers import find_numbers
from src.ingestion.real import Page

# generic header keywords per TEP field (RU/KZ), matched against repaired table headers
FIELD_HEADERS: dict[str, tuple[str, ...]] = {
    "floors": ("этажн", "қабат"),
    "building_area_m2": ("застройк", "құрылыс салу ауданы"),
    "construction_volume_m3": ("строительн\\w* объ[её]м", "құрылыс көлем", "объ[её]м"),
    "useful_area_m2": ("полезн", "пайдалы"),
    "total_area_m2": ("общ\\w* площад", "площад\\w* общ", "жалпы аудан"),
}


@dataclass
class ValueHit:
    object: str
    field: str
    expected: float
    where: str  # "table" | "text" | "none"
    column_ok: bool  # found in a table column whose header names the field
    table_pages: list[int]
    text_pages: list[int]
    hint_page: int | None
    on_hint_page: bool
    ambiguous: bool  # matched only through a secondary reading (e.g. 1,234 read as 1234)
    trivial: bool


def _eq(a: float, b: float) -> bool:
    return round(a, 2) == round(b, 2)


def _match(text: str, value: float) -> tuple[bool, bool]:
    """(found, found only via an ambiguous secondary reading)."""
    found = secondary = False
    for n in find_numbers(text):
        if _eq(n.value, value):
            found = True
        elif any(_eq(r, value) for r in n.readings[1:]):
            secondary = True
    return found or secondary, secondary and not found


def locate(pages: list[Page], obj: str, fld: str, value: float, hint_page: int | None) -> ValueHit:
    header_res = [re.compile(p, re.IGNORECASE) for p in FIELD_HEADERS.get(fld, ())]
    table_pages, text_pages, column_ok, ambiguous = set(), set(), False, False
    for page in pages:
        for table in page.tables:
            for row in table.rows[1:]:
                for col, cell in enumerate(row):
                    hit, amb = _match(cell, value)
                    if not hit:
                        continue
                    table_pages.add(page.number)
                    ambiguous |= amb
                    header = table.header[col] if col < len(table.header) else ""
                    column_ok |= any(r.search(header) for r in header_res)
        hit, amb = _match(page.text, value)
        if hit:
            text_pages.add(page.number)
            ambiguous |= amb
    where = "table" if table_pages else "text" if text_pages else "none"
    return ValueHit(obj, fld, value, where, column_ok, sorted(table_pages), sorted(text_pages - table_pages),
                    hint_page, hint_page in table_pages | text_pages, ambiguous,
                    float(value).is_integer() and abs(value) < 100)


def measure(ann: RealAnnotation, pages: list[Page]) -> list[ValueHit]:
    hits = []
    for obj, fields in ann.tep.items():
        hint = fields.get("page")
        for fld, raw in fields.items():
            if fld == "page":
                continue
            for value in raw if isinstance(raw, list) else [raw]:
                if isinstance(value, int | float) and not isinstance(value, bool):
                    hits.append(locate(pages, obj, fld, float(value), hint))
    return hits


def summary(hits: list[ValueHit]) -> dict:
    informative = [h for h in hits if not h.trivial]
    return {
        "values": len(hits),
        "informative_values": len(informative),
        "in_table": sum(h.where == "table" for h in informative),
        "in_table_right_column": sum(h.column_ok for h in informative),
        "text_only": sum(h.where == "text" for h in informative),
        "not_found": sum(h.where == "none" for h in informative),
        "ambiguous": sum(h.ambiguous for h in hits),
        "trivial": len(hits) - len(informative),
    }


def to_json(hits: list[ValueHit]) -> dict:
    return {"summary": summary(hits), "values": [asdict(h) for h in hits]}
