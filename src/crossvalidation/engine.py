"""Cross-section consistency checks over extracted TEP (language independent).

Input: per-section resolved extractions. Output: findings with a verdict
(MATCH / MISMATCH / MISSING), both values and their document locations, plus a
completeness block (which of ПЗ/АР/КР/смета were uploaded).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.ner.common.rules import Extraction
from src.ner.common.taxonomy import MANDATORY_TEP, MATERIALS, TOLERANCES, DiscrepancyType, Section, Verdict

REQUIRED_SECTIONS = (Section.PZ, Section.AR, Section.KR, Section.SMETA)

FIELD_LABELS_RU = {
    "total_area_m2": "Общая площадь здания", "explication_total_area_m2": "Итого по экспликации",
    "building_area_m2": "Площадь застройки", "construction_volume_m3": "Строительный объём",
    "estimated_cost_ktg": "Сметная стоимость строительства", "ssr.total_ktg": "Всего по сводному сметному расчёту",
    "os.total_ktg": "Итого по объектной смете", "concrete_b25_foundation_m3": "Бетон B25 (фундаменты)",
    "concrete_b30_frame_m3": "Бетон B30 (каркас)", "rebar_a500c_t": "Арматура A500С",
    "brick_masonry_m3": "Кирпичная кладка", "steel_structures_t": "Стальные конструкции",
    "floors": "Этажность", "useful_area_m2": "Полезная площадь", "underground_volume_m3": "Подземный объём",
    "construction_duration_months": "Продолжительность строительства", "seismicity_points": "Сейсмичность",
    "fire_resistance": "Степень огнестойкости",
}
SECTION_RU = {"PZ": "ПЗ", "AR": "АР", "KR": "КР", "SMETA": "Смета"}
UNIT_RU = {"m2": "м²", "m3": "м³", "t": "т", "kKZT": "тыс. тенге"}


def label(fld: str) -> str:
    base = fld.removeprefix("local_qty.")
    if base.startswith("ssr.ch2."):
        return f"Строка {base.split('os_')[1].removesuffix('_ktg')} в ССР (гл. 2)"
    return FIELD_LABELS_RU.get(base, base)


@dataclass
class Finding:
    type: str
    field: str
    verdict: str
    refs: list[dict]
    message: str
    delta_abs: float | None = None
    delta_rel: float | None = None
    notes: list[str] = field(default_factory=list)
    low_confidence: bool = False  # a value was read from a scan: verify by hand
    object: str | None = None  # building id for findings inside one ПЗ
    object_name: str | None = None
    needs_expert: bool = False  # the rule signals a likely error, not a certain one


def _ref(section: Section, fld: str, e: Extraction | None, derived: str | None = None) -> dict:
    d = {"section": section.value, "field": fld, "value": None if e is None else e.value}
    if e is not None:
        d |= {"raw": e.raw, "page": e.page, "bbox": e.bbox, "evidence": e.evidence, "source": e.source}
    if derived:
        d["derived"] = derived
    return d


def _compare(dtype: DiscrepancyType, fld: str, a: dict, b: dict, unit: str) -> Finding:
    va, vb = a["value"], b["value"]
    tol = TOLERANCES[dtype]
    ok = tol.matches(va, vb)
    delta = round(va - vb, 3)
    rel = round(delta / vb, 5) if vb else None
    sa, sb = SECTION_RU[a["section"]], SECTION_RU[b["section"]]
    if ok:
        msg = f"{label(fld)}: {sa} и {sb} совпадают ({va:g} {unit})."
    else:
        pct = f" ({rel:+.1%})" if rel is not None else ""
        msg = f"{label(fld)}: в {sa} {va:g} {unit}, в {sb} {vb:g} {unit}, расхождение {delta:+g}{pct}."
    return Finding(dtype.value, fld, (Verdict.MATCH if ok else Verdict.MISMATCH).value, [a, b], msg, delta, rel)


OCR_NOTE = "Значение прочитано со скана, сверьте вручную."


def check(tep: dict[Section, dict[str, Extraction]], rooms_sum: float | None,
          ocr_sections: frozenset[Section] = frozenset(),
          uploaded: frozenset[Section] | None = None) -> tuple[list[Finding], dict]:
    """Cross-section checks.

    `tep` holds the sections whose values may be compared (a multi-building ПЗ whose
    building could not be matched to the other sections is left out). `uploaded`
    lists every recognised section for the completeness block (defaults to `tep`).
    `ocr_sections`: sections read from scans; absence cannot be established from
    OCR, and comparisons involving them are low-confidence.
    MISSING is reported only with evidence: the reference section is uploaded and
    states the value, so the field is demonstrably part of this project.
    """
    uploaded = uploaded if uploaded is not None else frozenset(tep)
    present = [s for s in REQUIRED_SECTIONS if s in uploaded]
    completeness = {"required": [s.value for s in REQUIRED_SECTIONS], "present": [s.value for s in present],
                    "missing": [s.value for s in REQUIRED_SECTIONS if s not in uploaded]}
    findings: list[Finding] = []
    get = lambda s, f: tep.get(s, {}).get(f)  # noqa: E731

    # 1. Total area: ПЗ vs АР explication (fallback: sum of rooms)
    pz_area, ar_total = get(Section.PZ, "total_area_m2"), get(Section.AR, "explication_total_area_m2")
    if pz_area and (ar_total or rooms_sum):
        b = _ref(Section.AR, "explication_total_area_m2", ar_total)
        if ar_total is None:
            b |= {"value": rooms_sum, "derived": "сумма площадей помещений"}
        f = _compare(DiscrepancyType.AREA_PZ_VS_AR_EXPLICATION, "total_area_m2",
                     _ref(Section.PZ, "total_area_m2", pz_area), b, "м²")
        if ar_total is not None and rooms_sum is not None and abs(ar_total.value - rooms_sum) > 0.05:
            f.notes.append(f"В АР «Итого» ({ar_total.value:g}) не равно сумме помещений ({rooms_sum:g}).")
        findings.append(f)

    # 2. Materials: КР vs local estimate
    for m in MATERIALS:
        kr, ls = get(Section.KR, m), get(Section.SMETA, f"local_qty.{m}")
        if kr and ls:
            unit = "т" if m.endswith("_t") else "м³"
            findings.append(_compare(DiscrepancyType.MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE, m,
                                     _ref(Section.KR, m, kr), _ref(Section.SMETA, f"local_qty.{m}", ls), unit))

    # 3. Object estimate total vs its line in the summary estimate
    os_total = get(Section.SMETA, "os.total_ktg")
    ssr_lines = {f: e for f, e in tep.get(Section.SMETA, {}).items() if re.match(r"ssr\.ch2\.os_", f)}
    if os_total and len(ssr_lines) == 1:
        (fld, line), = ssr_lines.items()
        findings.append(_compare(DiscrepancyType.COST_OBJECT_ESTIMATE_VS_SUMMARY, fld,
                                 _ref(Section.SMETA, "os.total_ktg", os_total), _ref(Section.SMETA, fld, line),
                                 "тыс. тенге"))

    for f in findings:
        if any(r.get("source") == "ocr" for r in f.refs):
            f.low_confidence = True
            f.notes.append(OCR_NOTE)

    # 4. Mandatory TEP missing in an uploaded section (not decidable for scans)
    for (sec, fld), (ref_sec, ref_fld) in MANDATORY_TEP.items():
        if sec in tep and sec not in ocr_sections and get(sec, fld) is None:
            ref = get(ref_sec, ref_fld)
            if ref is None:  # no evidence that this project must state the value
                continue
            where = f", есть в {SECTION_RU[ref_sec.value]}: {ref.value:g}"
            findings.append(Finding(
                DiscrepancyType.MISSING_MANDATORY_TEP.value, fld, Verdict.MISSING.value,
                [_ref(sec, fld, None), _ref(ref_sec, ref_fld, ref)],
                f"{label(fld)}: не указан(а) в {SECTION_RU[sec.value]}{where}."))
    return findings, completeness
