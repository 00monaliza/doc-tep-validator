"""Rule-based checks v0 for real documents.

Findings use the annotation schema (``src.evaluation.schema.Finding``) so they
can be matched against manual ground truth. Implemented types:

* ``TABLE_TOTAL_MISMATCH``     — a "ИТОГО/Всего" row vs the sum of the rows above it;
* ``TEP_CROSS_SECTION_MISMATCH`` — one TEP of one object stated differently in
  several places (tables and sentences);
* ``PARAMETER_CONTRADICTION``  — several seismicity values in one document;
* ``GEOMETRY_INCONSISTENCY``   — building area smaller than the area within axes.

Logical and artifact levels are out of scope for v0. Nothing here knows the
concrete document: objects come from ``objects.py``, fields from
``field_patterns.py``. Values whose object cannot be resolved are not compared
and are reported in ``RuleReport.unresolved``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.crossvalidation.objects import SITE_RE, ObjectIndex, PageText, discover_objects, page_texts, resolve
from src.evaluation.schema import Finding, Ref
from src.ingestion.common.numbers import NUMBER_RE, normalize_unit, number_readings
from src.ingestion.real import Page, PageTable, norm_ws
from src.ner.common.field_patterns import FIELD_TEXT, FIELD_UNITS, header_field
from src.ner.common.taxonomy import TYPE_LEVEL, DiscrepancyType, Tolerance

TOTAL_RE = re.compile(r"^(?:итого|всего|барлығы|жиыны|жиынтығы)\b", re.IGNORECASE)
TEP_TOLERANCE = Tolerance(rel=0.005, abs=0.1)
GEOMETRY_TOLERANCE = Tolerance(rel=0.005, abs=0.1)
SUM_ABS_PER_ROW = 0.01  # rounding of every summed cell to 2 decimals

_UNIT = r"(?P<unit>[мm]\.?\s?[23²³]|кв\.\s?[мm]|куб\.\s?[мm])(?!\s*/)"
_NUM = rf"(?P<num>{NUMBER_RE.pattern})"
SEISMIC_RE = re.compile(r"(?:сейсмичн|сейсмикал)\w*\D{0,40}?(?P<num>\d{1,2})\s*балл\w*", re.IGNORECASE)
AXES_RE = re.compile(rf"в\s+осях\s+(?P<a>{NUMBER_RE.pattern})\s*[хx×*]\s*(?P<b>{NUMBER_RE.pattern})\s*м\b",
                     re.IGNORECASE)
AXES_KZ_RE = re.compile(rf"(?P<a>{NUMBER_RE.pattern})\s*[хx×*]\s*(?P<b>{NUMBER_RE.pattern})\s*м\b[^.]{{0,20}}?өстер",
                        re.IGNORECASE)


@dataclass
class Mention:
    object: str | None
    field: str
    value: float
    page: int
    quote: str
    source: str  # "table" | "text"
    how: str  # how the object was resolved


@dataclass
class RuleReport:
    findings: list[Finding] = field(default_factory=list)
    objects: dict[str, str] = field(default_factory=dict)  # id -> name, includes "site"/"document"
    mentions: list[Mention] = field(default_factory=list)
    unresolved: list[dict] = field(default_factory=list)


def _num(cell: str) -> float | None:
    readings = number_readings(cell)
    return readings[0] if readings else None


def _quote(page_text: str, *candidates: str) -> str:
    """The first candidate that occurs verbatim in the (normalized) page text."""
    for c in candidates:
        c = norm_ws(c)
        if c and c in page_text:
            return c
    raise ValueError(f"no candidate quote found on page: {candidates!r}")


def _row_quote(pt: PageText, row: list[str], col: int) -> str:
    return _quote(pt.text, " ".join(c for c in row if c), row[col])


def _finding(dtype: DiscrepancyType, fld: str, obj: str, refs: list[Ref], confidence: str = "certain",
             note: str = "", delta_rel: float | None = None) -> Finding:
    return Finding(id="", level=TYPE_LEVEL[dtype], type=dtype, field=fld, object=obj, refs=refs,
                   confidence=confidence, note=note, delta_rel=delta_rel)


# ------------------------------------------------------------------ tables
def _table_object(pt: PageText, table: PageTable, carried: str | None) -> str | None:
    return pt.context_above(table.top, carried)


def check_table_totals(pages: list[Page], pts: list[PageText], carried: list[str | None]) -> list[Finding]:
    out = []
    for page, pt, car in zip(pages, pts, carried, strict=True):
        for table in page.tables:
            obj = _table_object(pt, table, car) or "document"
            block: list[list[str]] = []
            for row in table.rows[1:]:
                first = next((c for c in row if c), "")
                if not TOTAL_RE.match(first):
                    if any(_num(c) is not None for c in row):
                        block.append(row)
                    continue
                for col, cell in enumerate(row):
                    total = _num(cell)
                    values = [v for r in block if col < len(r) and (v := _num(r[col])) is not None]
                    if total is None or not values:
                        continue
                    s = round(sum(values), 6)
                    if abs(s - total) <= SUM_ABS_PER_ROW * len(values) + 1e-9:
                        continue
                    header = table.header[col] if col < len(table.header) else ""
                    fld = header_field(header) or f"col:{header or col}"
                    refs = [Ref(page=page.number, quote=_row_quote(pt, r, col), object=obj, value=_num(r[col]),
                                col=header or None) for r in block if col < len(r) and _num(r[col]) is not None]
                    refs.append(Ref(page=page.number, quote=_row_quote(pt, row, col), object=obj, value=total,
                                    row=first, col=header or None))
                    out.append(_finding(DiscrepancyType.TABLE_TOTAL_MISMATCH, fld, obj, refs,
                                        note=f"sum of rows {s:g} != total {total:g}",
                                        delta_rel=round((total - s) / s, 5) if s else None))
                block = []
    return out


def table_mentions(pages: list[Page], pts: list[PageText], carried: list[str | None],
                   index: ObjectIndex) -> list[Mention]:
    """TEP values from data rows of tables whose header names a TEP field."""
    out = []
    for page, pt, car in zip(pages, pts, carried, strict=True):
        for table in page.tables:
            cols = {i: f for i, h in enumerate(table.header) if (f := header_field(h)) in FIELD_UNITS}
            if not cols:
                continue
            ctx = _table_object(pt, table, car)
            for row in table.rows[1:]:
                first = next((c for c in row if c), "")
                if TOTAL_RE.match(first):
                    continue
                label = row[0] if row else ""
                named = index.mentioned(label) if label else set()
                obj, how = (next(iter(named)), "row label") if len(named) == 1 else (ctx, "heading")
                for col, fld in cols.items():
                    value = _num(row[col]) if col < len(row) else None
                    if value is not None:
                        out.append(Mention(obj, fld, value, page.number, _row_quote(pt, row, col), "table",
                                           how if obj else "no heading or mention"))
    return out


# ------------------------------------------------------------------ text
def text_mentions(pts: list[PageText], index: ObjectIndex) -> list[Mention]:
    out = []
    for pt in pts:
        for fld, labels in FIELD_TEXT.items():
            for label in labels:
                rx = re.compile(rf"{label}[^\d.;:]{{0,60}}?{_NUM}\s*{_UNIT}", re.IGNORECASE)
                for m in rx.finditer(pt.text):
                    if normalize_unit(m.group("unit")) != FIELD_UNITS[fld]:
                        continue
                    value = _num(m.group("num"))
                    if value is None:
                        continue
                    obj, how = resolve(pt, index, m.start(), m.end())
                    out.append(Mention(obj, fld, value, pt.page, _quote(pt.text, m.group()), "text", how))
    # the same phrase can match several label variants
    seen, unique = set(), []
    for mt in out:
        key = (mt.page, mt.field, mt.value, mt.quote)
        if key not in seen:
            seen.add(key)
            unique.append(mt)
    return unique


def check_cross_section(mentions: list[Mention]) -> list[Finding]:
    groups: dict[tuple[str, str], list[Mention]] = {}
    for m in mentions:
        if m.object:
            groups.setdefault((m.object, m.field), []).append(m)
    out = []
    for (obj, fld), ms in groups.items():
        base = ms[0]
        for other in ms[1:]:
            if TEP_TOLERANCE.matches(base.value, other.value):
                continue
            if (base.page, base.source) == (other.page, other.source):
                continue  # two rows of one table are not "different places"
            refs = [Ref(page=m.page, quote=m.quote, object=obj, value=m.value, unit=FIELD_UNITS[fld])
                    for m in (base, other)]
            out.append(_finding(DiscrepancyType.TEP_CROSS_SECTION_MISMATCH, fld, obj, refs,
                                delta_rel=round((base.value - other.value) / other.value, 5),
                                note=f"{base.source} p.{base.page} vs {other.source} p.{other.page}"))
            break  # one finding per (object, field)
    return out


def check_seismicity(pts: list[PageText], index: ObjectIndex) -> list[Finding]:
    """Seismicity is a property of the site: more than one value in the document is a contradiction."""
    refs = []
    for pt in pts:
        for m in SEISMIC_RE.finditer(pt.text):
            obj, _ = resolve(pt, index, m.start(), m.end())
            if SITE_RE.search(pt.sentence(m.start(), m.end())) and obj is None:
                obj = "site"
            refs.append(Ref(page=pt.page, quote=_quote(pt.text, m.group()), object=obj or "site",
                            value=int(m.group("num"))))
    if len({r.value for r in refs}) < 2:
        return []
    return [_finding(DiscrepancyType.PARAMETER_CONTRADICTION, "seismicity_points", "site", refs,
                     note="values: " + ", ".join(str(v) for v in sorted({r.value for r in refs})))]


def check_geometry(pts: list[PageText], index: ObjectIndex, mentions: list[Mention],
                   unresolved: list[dict]) -> list[Finding]:
    """Building area (outer contour) must not be smaller than the area within the axes."""
    out = []
    areas: dict[str, list[Mention]] = {}
    for m in mentions:
        if m.object and m.field == "building_area_m2":
            areas.setdefault(m.object, []).append(m)
    for pt in pts:
        for rx in (AXES_RE, AXES_KZ_RE):
            for m in rx.finditer(pt.text):
                a, b = _num(m.group("a")), _num(m.group("b"))
                if a is None or b is None:
                    continue
                obj, how = resolve(pt, index, m.start(), m.end())
                if obj is None:
                    unresolved.append({"rule": "GEOMETRY_INCONSISTENCY", "page": pt.page, "quote": m.group(),
                                       "reason": how})
                    continue
                axes_area = round(a * b, 2)
                for area in areas.get(obj, []):
                    if area.value < axes_area and not GEOMETRY_TOLERANCE.matches(area.value, axes_area):
                        refs = [Ref(page=pt.page, quote=_quote(pt.text, m.group()), object=obj, value=axes_area,
                                    unit="m2", derived=f"{a:g} x {b:g}"),
                                Ref(page=area.page, quote=area.quote, object=obj, value=area.value, unit="m2")]
                        out.append(_finding(DiscrepancyType.GEOMETRY_INCONSISTENCY, "building_area_m2", obj, refs,
                                            confidence="needs_expert",
                                            note=f"building area {area.value:g} < area within axes {axes_area:g}"))
                        break
    return out


def run_rules(pages: list[Page]) -> RuleReport:
    index = discover_objects(pages)
    pts = page_texts(pages, index)
    carried = [None] + [pt.ctx_after for pt in pts[:-1]]
    report = RuleReport(objects={o.id: o.name for o in index.objects} | {"site": "Площадка",
                                                                          "document": "Документ в целом"})
    report.mentions = table_mentions(pages, pts, carried, index) + text_mentions(pts, index)
    for m in report.mentions:
        if m.object is None:
            report.unresolved.append({"rule": "TEP_CROSS_SECTION_MISMATCH", "page": m.page, "quote": m.quote,
                                      "field": m.field, "value": m.value, "reason": m.how})
    findings = (check_table_totals(pages, pts, carried)
                + check_cross_section(report.mentions)
                + check_seismicity(pts, index)
                + check_geometry(pts, index, report.mentions, report.unresolved))
    for i, f in enumerate(findings, start=1):
        f.id = f"P{i}"
    report.findings = findings
    return report
