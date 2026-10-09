"""Rule-based TEP extractor (baseline): tables first, paragraph regexes as fallback.

Works on a `Layout` (text-layer PDF). RU and KZ patterns are merged, so a
document mixing both languages is still handled. Every extraction keeps its
page, bounding box and the evidence text for the report / viewer highlight.
Field ids are the ground-truth ids (see src/ner/common/taxonomy.py).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from src.ingestion.common.layout import BBox, Layout, Line, Table
from src.ner.common.taxonomy import Section
from src.ner.kz import rules as kz
from src.ner.ru import rules as ru
from src.synthesis.formatting import parse_num

LANGS = (ru, kz)
NUM = r"\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
NUM_RE = re.compile(rf"^(?:{NUM})$")
NUM_IN_TEXT = re.compile(rf"(?<![\d,.])({NUM})(?![\d])")


def _any(key: str, attr: str) -> str:
    """Union of a pattern across languages, e.g. _any('label', 'HEADER')."""
    return "|".join(f"(?:{getattr(lang, attr)[key]})" for lang in LANGS)


def _search(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def _field_by_label(label: str, table_attr: str) -> str | None:
    for lang in LANGS:
        for fld, pat in getattr(lang, table_attr):
            if _search(pat, label):
                return fld
    return None


@dataclass
class Extraction:
    section: str
    field: str
    value: float
    raw: str  # value text as in the document
    page: int
    bbox: BBox | None
    source: str  # table | text
    evidence: str  # row / sentence the value was taken from
    method: str = "exact"  # how the TEP label was recognised (label_match stage)

    def to_json(self) -> dict:
        return asdict(self)


def _num(text: str) -> float | None:
    text = text.strip()
    return parse_num(text) if NUM_RE.match(text) else None


def _table_kind(t: Table) -> str:
    header = " ".join(t.header)
    ctx = t.context
    if _search(_any("price", "HEADER"), header):
        return "local"
    if _search(_any("estimate_no", "HEADER"), header):
        if _search(_any("summary", "TABLE_CONTEXT"), ctx):
            return "summary"
        if _search(_any("object", "TABLE_CONTEXT"), ctx):
            return "object"
        return "estimate_unknown"
    if _search(_any("explication", "TABLE_CONTEXT"), ctx) or _search(r"№ ?пом|үй-жай №", header):
        return "explication"
    if _search(_any("qty", "HEADER"), header) and _search(_any("materials", "TABLE_CONTEXT"), ctx + header):
        return "materials"
    if _search(_any("value", "HEADER"), header):
        return "tep"
    return "unknown"


def _label_text(row: list, skip: set[int]) -> str:
    return " ".join(c.text for i, c in enumerate(row) if i not in skip and c.text and _num(c.text) is None)


def _cost_scale(unit_text: str) -> float:
    """Convert a cost to thousands of tenge."""
    if _search(r"млн", unit_text):
        return 1000.0
    if _search(_any_attr("COST_UNIT_THOUSANDS"), unit_text):
        return 1.0
    if _search(r"тенге|теңге|тг", unit_text):
        return 0.001
    return 1.0


def _any_attr(attr: str) -> str:
    return "|".join(f"(?:{getattr(lang, attr)})" for lang in LANGS)


def _extract_table(section: Section, t: Table) -> list[Extraction]:
    out: list[Extraction] = []
    kind = _table_kind(t)
    col = {k: t.column(_any(k, "HEADER")) for k in ("label", "value", "qty", "area", "estimate_no", "unit")}

    def emit(fld: str, row: list, c: int, value: float | None = None) -> None:
        cell = row[c]
        v = value if value is not None else _num(cell.text)
        if v is None:
            return
        out.append(Extraction(section.value, fld, v, cell.text, cell.page, cell.bbox, "table",
                              " | ".join(x.text for x in row if x.text)))

    for row in t.rows:
        label = _label_text(row, set())
        if kind == "tep":
            vcol = col["value"] if col["value"] is not None else len(row) - 1
            fld = _field_by_label(label, "TEP_ROW")
            if fld is None:
                continue
            if fld == "estimated_cost_ktg":
                unit = row[col["unit"]].text if col["unit"] is not None else label
                v = _num(row[vcol].text)
                if v is not None:
                    emit(fld, row, vcol, round(v * _cost_scale(unit + " " + label), 3))
                continue
            if fld == "floors":
                v = _num(row[vcol].text)
                emit(fld, row, vcol, int(v) if v is not None else None)
                continue
            emit(fld, row, vcol)
        elif kind == "explication":
            acol = col["area"] if col["area"] is not None else len(row) - 2
            if _search(_any("floor_subtotal", "TOTAL_ROW"), label):
                continue
            if _search(_any("explication_total", "TOTAL_ROW"), label):
                emit("explication_total_area_m2", row, acol)
            elif re.fullmatch(r"\d{1,4}[а-яa-z]?", row[0].text or ""):
                emit(f"room.{row[0].text}.area_m2", row, acol)
        elif kind in ("materials", "local"):
            qcol = col["qty"]
            fld = _field_by_label(label, "MATERIAL_ROW")
            if fld is not None and qcol is not None:
                emit(fld if kind == "materials" else f"local_qty.{fld}", row, qcol)
            elif kind == "local" and _search(_any("local_total", "TOTAL_ROW"), label):
                emit("local.total_tg", row, len(row) - 1)
        elif kind == "object":
            if _search(_any("object_total", "TOTAL_ROW"), label):
                emit("os.total_ktg", row, len(row) - 1)
        elif kind == "summary":
            ecol = col["estimate_no"]
            ref = row[ecol].text if ecol is not None else ""
            if m := re.match(r"(?:ОС|OC|ОC)\s*(\d{2}-\d{2})", ref):
                emit(f"ssr.ch2.os_{m.group(1)}_ktg", row, len(row) - 1)
            elif _search(_any("summary_total", "TOTAL_ROW"), label):
                emit("ssr.total_ktg", row, len(row) - 1)
    return out


def _paragraphs(lines: list[Line]) -> list[tuple[str, list[tuple[int, Line]]]]:
    """Join lines of each page into one text with a char-offset -> line map."""
    by_page: dict[int, list[Line]] = {}
    for ln in lines:
        by_page.setdefault(ln.page, []).append(ln)
    out = []
    for page_lines in by_page.values():
        text, spans = "", []
        for ln in page_lines:
            spans.append((len(text), ln))
            text += ln.text + " "
        out.append((text, spans))
    return out


def _line_at(spans: list[tuple[int, Line]], pos: int) -> Line:
    return [ln for start, ln in spans if start <= pos][-1]


def _extract_text(section: Section, lines: list[Line]) -> list[Extraction]:
    out = []
    for text, spans in _paragraphs(lines):
        for fld in ("total_area_m2", "construction_volume_m3", "estimated_cost_ktg", "concrete_total_m3"):
            for m in re.finditer(_any(fld, "PARAGRAPH"), text, re.IGNORECASE):
                window = text[m.end(): m.end() + 120]
                n = NUM_IN_TEXT.search(window)
                if n is None:
                    continue
                value = parse_num(n.group(1))
                if fld == "estimated_cost_ktg":
                    after = window[n.end(): n.end() + 20]
                    if not _search(_any_attr("COST_UNIT_THOUSANDS") + r"|тенге|теңге", after):
                        continue
                    value = round(value * _cost_scale(after), 3)
                ln = _line_at(spans, m.end() + n.start())
                sentence = text[max(0, m.start() - 20): m.end() + n.end() + 10].strip()
                out.append(Extraction(section.value, fld, value, n.group(1), ln.page, ln.bbox, "text", sentence))
                break
        for pat in (ru.FLOORS_IN_TEXT, kz.FLOORS_IN_TEXT):
            if m := re.search(pat, text):
                ln = _line_at(spans, m.start())
                out.append(Extraction(section.value, "floors", int(m.group(1)), m.group(1), ln.page, ln.bbox,
                                      "text", text[max(0, m.start() - 20): m.end() + 20].strip()))
    return out


def extract(section: Section, layout: Layout) -> list[Extraction]:
    """All extractions for one document (tables + text), in reading order."""
    out: list[Extraction] = []
    for table in layout.tables:
        out.extend(_extract_table(section, table))
    out.extend(_extract_text(section, layout.lines))
    return out


UNIT_THEN_NUM = re.compile(rf"(?:м³|м²|м3|м2|(?<![^\W\d_])т(?![^\W\d_]))[\s|]*({NUM})")


def extract_ocr_lines(section: Section, layout: Layout) -> list[Extraction]:
    """Scan path: no table structure, so each OCR line is treated as a potential table row
    (label + trailing number). Less reliable than `extract`; room rows are not attempted."""
    out = _extract_text(section, layout.lines)
    for ln in layout.lines:
        def after(pattern: str, ln: Line = ln) -> str | None:
            """First number after the label (row numbers precede labels, other values follow)."""
            m = re.search(pattern, ln.text, re.IGNORECASE)
            n = NUM_IN_TEXT.search(ln.text, m.end()) if m else None
            return n.group(1) if n else None

        def emit(fld: str, raw: str | None, value: float | None = None, ln: Line = ln) -> None:
            if raw is None:
                return
            v = value if value is not None else parse_num(raw)
            out.append(Extraction(section.value, fld, v, raw, ln.page, None, "ocr", ln.text))

        def label_pattern(table_attr: str, fld: str) -> str:
            return "|".join(f"(?:{p})" for lang in LANGS for f, p in getattr(lang, table_attr) if f == fld)

        if section in (Section.PZ, Section.AR):
            if section == Section.AR and _search(_any("explication_total", "TOTAL_ROW"), ln.text) \
                    and not _search(_any("floor_subtotal", "TOTAL_ROW"), ln.text):
                emit("explication_total_area_m2", after(_any("explication_total", "TOTAL_ROW")))
                continue
            fld = _field_by_label(ln.text, "TEP_ROW")
            if fld is None:
                continue
            raw = after(label_pattern("TEP_ROW", fld))
            if raw is None:
                continue
            if fld == "floors":
                emit(fld, raw, int(parse_num(raw)))
            elif fld == "estimated_cost_ktg":
                emit(fld, raw, round(parse_num(raw) * _cost_scale(ln.text), 3))
            else:
                emit(fld, raw)
        elif section == Section.KR:
            if (fld := _field_by_label(ln.text, "MATERIAL_ROW")) is not None:
                emit(fld, after(label_pattern("MATERIAL_ROW", fld)))
        elif section == Section.SMETA:
            if (fld := _field_by_label(ln.text, "MATERIAL_ROW")) is not None:
                if m := UNIT_THEN_NUM.search(ln.text):
                    emit(f"local_qty.{fld}", m.group(1))
            elif m := re.search(r"(?:ОС|OC)\s*(\d{2}-\d{2})", ln.text):
                nums = NUM_IN_TEXT.findall(ln.text[m.end():])
                emit(f"ssr.ch2.os_{m.group(1)}_ktg", nums[-1] if nums else None)
            elif _search(_any("object_total", "TOTAL_ROW"), ln.text):
                emit("os.total_ktg", after(_any("object_total", "TOTAL_ROW")))
            elif _search(_any("summary_total", "TOTAL_ROW"), ln.text):
                emit("ssr.total_ktg", after(_any("summary_total", "TOTAL_ROW")))
    return out


def resolve(extractions: list[Extraction]) -> dict[str, Extraction]:
    """One value per field: tables win over text; first occurrence otherwise."""
    best: dict[str, Extraction] = {}
    for e in sorted(extractions, key=lambda e: e.source != "table"):
        best.setdefault(e.field, e)
    return best
