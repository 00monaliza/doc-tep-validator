"""End-to-end analysis of a document package: files -> TEP -> cross-checks -> report.

* ПЗ with a text layer: the lexicon extractor (``ner.common.tep_baseline``) reads
  TEP per building, and rules v0 (``crossvalidation.rules``) check the note
  itself: table totals, one TEP stated differently, seismicity, geometry.
* АР, КР, смета and DOCX: section-specific table rules (``ner.common.rules``).
* Image-only PDFs (scans): Tesseract + unit normalisation in line mode, which
  is less reliable; such documents are flagged in the report.

Cross-section checks (``crossvalidation.engine``) then compare the sections. A
ПЗ may describe several buildings; it is compared with АР/КР/смета only for
the building those sections are about (matched by the object name in their
title), otherwise the comparison is skipped with a warning.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

from src.crossvalidation.engine import Finding, check
from src.crossvalidation.report import doc_object_name, match_building, pz_findings, pz_tep
from src.crossvalidation.rules import run_rules
from src.ingestion.common.classify import detect_language, detect_section
from src.ingestion.common.layout import Layout, Line, parse_docx, parse_pdf
from src.ingestion.common.locate import Locator
from src.ingestion.common.normalize import normalize_units
from src.ingestion.common.ocr import ocr_image
from src.ingestion.common.pdf import rasterize
from src.ingestion.real import load_pages
from src.ner.common.rules import Extraction, extract, extract_ocr_lines, resolve
from src.ner.common.taxonomy import Section
from src.ner.common.tep_baseline import PROJECT
from src.ner.common.tep_baseline import extract as extract_pz

OCR_DPI = 300
PROJECT_FIELDS = ("estimated_cost_ktg", "construction_duration_months", "underground_volume_m3")


def _ocr_layout(path: Path) -> tuple[Layout, str]:
    pages = rasterize(path, dpi=OCR_DPI)
    raw = [ocr_image(img, "kz") for img in pages]  # kaz model also covers Russian Cyrillic
    lang = detect_language(" ".join(raw))
    if lang == "ru":
        raw = [ocr_image(img, "ru") for img in pages]
    layout = Layout(str(path), len(pages))
    for page_no, text in enumerate(raw, start=1):
        text, _ = normalize_units(text)
        layout.items.extend(Line(t.strip(), page_no, None) for t in text.split("\n") if t.strip())
    return layout, lang


def analyze_document(path: Path, loc: Locator) -> dict:
    ocr = False
    if path.suffix.lower() == ".docx":
        layout = parse_docx(path)
        lang = detect_language(layout.text() + " ".join(" ".join(t.header) for t in layout.tables))
    else:
        layout = parse_pdf(path)
        if layout.has_text():
            lang = detect_language(layout.text())
        else:
            layout, lang = _ocr_layout(path)
            ocr = True
    section, how = detect_section(layout)
    doc = {"file": path.name, "path": str(path), "lang": lang, "section": section.value if section else None,
           "section_detected_by": how, "pages": layout.n_pages, "ocr": ocr, "object_title": doc_object_name(layout),
           "_extractions": [], "_objects": {}, "_by_object": {}, "_findings": []}

    if section == Section.PZ and path.suffix.lower() == ".pdf" and not ocr:
        pages = load_pages(path)
        ex = extract_pz(pages)
        doc["_objects"] = ex.objects
        doc["_by_object"] = pz_tep(ex, path, loc)
        v0 = run_rules(pages)
        names = ex.objects | {k: v for k, v in v0.objects.items() if k not in ex.objects}
        doc["_findings"] = pz_findings(v0.findings, names, path, loc)
    elif section is not None:
        doc["_extractions"] = extract_ocr_lines(section, layout) if ocr else extract(section, layout)
    doc["extractions"] = [e.to_json() for e in doc["_extractions"]] + [
        e.to_json() | {"object": obj} for obj, fields in doc["_by_object"].items() for e in fields.values()]
    return doc


def _pz_for_engine(pz: dict, others: list[dict]) -> tuple[dict[str, Extraction] | None, str | None, str | None]:
    """ПЗ values comparable with the other sections: (fields, building id, warning)."""
    by_obj: dict[str, dict[str, Extraction]] = pz["_by_object"]
    if not by_obj:  # DOCX / scan: section-level extraction, single building assumed
        return resolve(pz["_extractions"]), None, None
    project = by_obj.get(PROJECT, {})
    buildings = {i: n for i, n in pz["_objects"].items() if i != PROJECT}
    if not others:
        return None, None, None
    building = match_building(pz["_objects"], [d["object_title"] for d in others if d["object_title"]])
    if building is None and buildings:
        names = ", ".join(buildings.values())
        return None, None, (f"ПЗ описывает {len(buildings)} здания ({names}), и по заголовкам АР/КР/сметы не "
                            f"удалось понять, к какому они относятся. Сверка ПЗ с другими разделами не выполнена.")
    fields = dict(by_obj.get(building, {})) if building else {}
    for fld in PROJECT_FIELDS:  # project-level values belong to the whole object
        if fld not in fields and fld in project:
            fields[fld] = project[fld]
    if not buildings:
        fields = {**project, **fields}
    return fields, building, None


def analyze_package(paths: list[Path]) -> dict:
    loc = Locator()
    try:
        docs = [analyze_document(Path(p), loc) for p in paths]
    finally:
        loc.close()
    warnings: list[str] = []
    by_section: dict[Section, dict] = {}
    duplicates = []
    for d in docs:
        if d["section"] is None:
            continue
        sec = Section(d["section"])
        if sec in by_section:
            duplicates.append(d["file"])
            continue
        by_section[sec] = d

    tep: dict[Section, dict[str, Extraction]] = {s: resolve(d["_extractions"])
                                                 for s, d in by_section.items() if s != Section.PZ}
    pz_building = None
    if Section.PZ in by_section:
        pz = by_section[Section.PZ]
        others = [d for s, d in by_section.items() if s != Section.PZ]
        fields, pz_building, warn = _pz_for_engine(pz, others)
        if fields is not None:
            tep[Section.PZ] = fields
        if warn:
            warnings.append(warn)

    rooms = [e.value for f, e in tep.get(Section.AR, {}).items() if re.match(r"room\.", f)]
    ocr_sections = frozenset(Section(d["section"]) for d in docs if d["ocr"] and d["section"])
    cross, completeness = check(tep, round(sum(rooms), 2) if rooms else None, ocr_sections, frozenset(by_section))
    pz_doc = by_section.get(Section.PZ)
    inner: list[Finding] = pz_doc["_findings"] if pz_doc else []
    objects = dict(pz_doc["_objects"]) if pz_doc else {}
    if pz_building:
        for f in cross:
            f.object, f.object_name = pz_building, objects.get(pz_building)

    scans = [d["file"] for d in docs if d["ocr"]]
    if scans:
        warnings.append(f"Без текстового слоя (сканы): {', '.join(scans)}. Таблицы на сканах распознаются "
                        f"ненадёжно: часть проверок пропущена, отсутствие показателей не проверяется.")
    for d in docs:
        if d["section"] is None:
            warnings.append(f"{d['file']}: не удалось определить раздел документа.")
        elif not d["extractions"]:
            warnings.append(f"{d['file']}: не найдено ни одного ТЭП.")

    tep_out = {s.value: {f: e.to_json() for f, e in fields.items()} for s, fields in tep.items() if s != Section.PZ}
    if pz_doc:
        if pz_doc["_by_object"]:
            tep_out["PZ"] = {f"{obj}/{f}": e.to_json() | {"object": obj}
                             for obj, fields in pz_doc["_by_object"].items() for f, e in fields.items()}
        else:
            tep_out["PZ"] = {f: e.to_json() for f, e in tep.get(Section.PZ, {}).items()}
    findings = inner + cross
    for d in docs:
        for k in [k for k in d if k.startswith("_")]:
            del d[k]
    langs = {d["lang"] for d in docs}
    return {
        "lang": langs.pop() if len(langs) == 1 else "mixed",
        "warnings": warnings,
        "documents": docs,
        "objects": objects,
        "pz_building": pz_building,
        "completeness": completeness | {"unrecognised": [d["file"] for d in docs if d["section"] is None],
                                        "duplicates": duplicates},
        "tep": tep_out,
        "findings": [asdict(f) for f in findings],
        "summary": {v: sum(f.verdict == v for f in findings) for v in ("MISMATCH", "MISSING", "MATCH")},
    }
