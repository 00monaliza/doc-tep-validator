"""Adapters from the real-document code (tep_baseline, rules v0) to the service report.

* ``pz_tep``: per-building TEP of a ПЗ as report extractions with page + bbox;
* ``pz_findings``: rules v0 findings (schema.Finding) as report findings with
  Russian messages, object names and highlight boxes;
* ``match_building``: which building of a multi-building ПЗ the other sections
  (АР, КР, смета) describe, by the object name in their title.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.crossvalidation.engine import SECTION_RU, Finding, label
from src.crossvalidation.objects import build_index
from src.evaluation.schema import Finding as V0Finding
from src.ingestion.common.layout import Layout
from src.ingestion.common.locate import Locator, raw_number
from src.ner.common.rules import Extraction
from src.ner.common.taxonomy import DiscrepancyType, Section, Verdict
from src.ner.common.tep_baseline import PROJECT
from src.ner.common.tep_baseline import Extraction as PzExtraction

UNIT_RU = {"m2": "м²", "m3": "м³", "t": "т", "floor": "эт.", "month": "мес.", "kKZT": "тыс. тенге"}
SOURCE_RU = {"table_h": "таблица", "table_v": "таблица", "text": "текст", "table": "таблица"}
SPECIAL_OBJECTS = {"site": "Площадка", "document": "Документ в целом", "all": "Все здания", PROJECT: "Проект в целом"}


def axes_ru(derived: str | None) -> str:
    """'8.5 x 24' -> '8,5 × 24'."""
    return re.sub(r"(?<=\d)\.(?=\d)", ",", (derived or "").replace("x", "×"))


def fmt(v: float | None) -> str:
    if v is None:
        return "—"
    s = f"{v:,.3f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",")
    return s


# ------------------------------------------------------------------ TEP
def pz_tep(ex: PzExtraction, path: Path, loc: Locator) -> dict[str, dict[str, Extraction]]:
    """object id -> field -> extraction (the value chosen for that slot)."""
    out: dict[str, dict[str, Extraction]] = {}
    for (obj, fld), c in ex.slots.items():
        raw = raw_number(c.quote, c.value) or fmt(c.value)
        out.setdefault(obj, {})[fld] = Extraction(
            Section.PZ.value, fld, c.value, raw, c.page, loc.bbox(path, c.page, c.quote, raw),
            "table" if c.source.startswith("table") else "text", c.quote)
    return out


def doc_object_name(layout: Layout) -> str | None:
    """Object name from the first «…» on page 1 (title block of АР / КР / смета)."""
    for ln in layout.lines:
        if ln.page != 1:
            break
        if m := re.search(r"«([^»]{4,})»", ln.text):
            return m.group(1)
    return None


def match_building(objects: dict[str, str], titles: list[str]) -> str | None:
    """The single building mentioned by the titles of the other sections, if unambiguous."""
    buildings = {i: n for i, n in objects.items() if i != PROJECT}
    if len(buildings) == 1:
        return next(iter(buildings))
    if not buildings or not titles:
        return None
    index = build_index(list(buildings.values()))
    by_name = {n: i for i, n in buildings.items()}
    hits = set()
    for t in titles:
        hits |= {by_name[o.name] for o in index.objects if o.id in index.mentioned(t)}
    return next(iter(hits)) if len(hits) == 1 else None


# ------------------------------------------------------------------ findings
def _obj_name(obj: str | None, objects: dict[str, str]) -> str:
    return SPECIAL_OBJECTS.get(obj or "", objects.get(obj or "", obj or ""))


def _ref(path: Path, loc: Locator, page: int, quote: str, value: float | None, ref_label: str,
         fld: str, obj: str | None, derived: str | None = None) -> dict:
    if isinstance(value, str):  # categorical value, e.g. fire resistance degree "II"
        raw = value
    else:
        raw = raw_number(quote, value) if value is not None else None
        raw = raw or (fmt(value) if value else None)
    return {"section": Section.PZ.value, "field": fld, "value": value, "raw": raw,
            "page": page, "bbox": loc.bbox(path, page, quote, raw), "evidence": quote, "source": "table",
            "label": ref_label, "object": obj, **({"derived": derived} if derived else {})}


def pz_findings(v0: list[V0Finding], objects: dict[str, str], path: Path, loc: Locator) -> list[Finding]:
    out = []
    for f in v0:
        name = _obj_name(f.object, objects)
        where = f" ({name})" if f.object not in ("document", None) else ""
        fld_label = label(f.field) if not f.field.startswith("col:") else f.field[4:]
        refs: list[dict]
        if f.type == DiscrepancyType.TABLE_TOTAL_MISMATCH:
            total = f.refs[-1]
            rows = f.refs[:-1]
            s = round(sum(r.value for r in rows), 3)
            refs = [_ref(path, loc, total.page, total.quote, total.value, "Итого", f.field, f.object),
                    _ref(path, loc, rows[0].page, rows[0].quote, rows[0].value, f"Строки ({len(rows)})",
                         f.field, f.object, derived=f"сумма {len(rows)} строк = {fmt(s)}") | {"value": s}]
            msg = f"{fld_label}{where}: в строке «Итого» {fmt(total.value)}, а сумма строк {fmt(s)}."
            delta = round(total.value - s, 3)
        elif f.type == DiscrepancyType.PARAMETER_CONTRADICTION:
            refs = [_ref(path, loc, r.page, r.quote, r.value, f"стр. {r.page}", f.field, r.object)
                    for r in f.refs]
            if f.field == "fire_resistance":
                values = ", ".join(sorted({str(r.value) for r in f.refs}))
                msg = f"Степень огнестойкости{where}: в документе указаны разные значения: {values}."
            else:
                values = ", ".join(sorted({str(int(r.value)) for r in f.refs}))
                msg = f"Сейсмичность{where}: в документе указаны разные значения: {values} балл(а)."
            delta = None
        elif f.type == DiscrepancyType.GEOMETRY_INCONSISTENCY:
            axes, area = f.refs
            refs = [_ref(path, loc, area.page, area.quote, area.value, f"Площадь, стр. {area.page}", f.field, f.object),
                    _ref(path, loc, axes.page, axes.quote, axes.value, f"Оси, стр. {axes.page}", f.field, f.object,
                         derived=f"площадь в осях {axes_ru(axes.derived)}")]
            msg = (f"Площадь застройки{where} {fmt(area.value)} м² меньше площади в осях {fmt(axes.value)} м² "
                   f"({axes_ru(axes.derived)}).")
            delta = round(area.value - axes.value, 3)
        else:  # TEP_CROSS_SECTION_MISMATCH and anything new: two places, two values
            a, b = f.refs[0], f.refs[1]
            unit = UNIT_RU.get(a.unit or "", "")
            refs = [_ref(path, loc, r.page, r.quote, r.value, f"стр. {r.page}", f.field, r.object) for r in (a, b)]
            msg = (f"{fld_label}{where}: {fmt(a.value)} {unit} на стр. {a.page} и {fmt(b.value)} {unit} "
                   f"на стр. {b.page}.")
            delta = round(a.value - b.value, 3) if a.value is not None and b.value is not None else None
        finding = Finding(f.type.value, f.field, Verdict.MISMATCH.value, refs, msg, delta, f.delta_rel)
        finding.object = f.object
        finding.object_name = name
        if f.confidence == "needs_expert":
            finding.needs_expert = True
            finding.notes.append("Требует оценки эксперта: правило указывает на возможную ошибку, не на точную.")
        out.append(finding)
    return out


def section_label(section: str) -> str:
    return SECTION_RU.get(section, section)
