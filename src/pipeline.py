"""End-to-end analysis of a document package: files -> TEP -> cross-checks -> report.

Text-layer PDFs and DOCX go through tables + text rules. Image-only PDFs
(scans) go through Tesseract + unit normalisation in line mode, which is
less reliable; such documents are flagged in the report.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

from src.crossvalidation.engine import check
from src.ingestion.common.classify import detect_language, detect_section
from src.ingestion.common.layout import Layout, Line, parse_docx, parse_pdf
from src.ingestion.common.normalize import normalize_units
from src.ingestion.common.ocr import ocr_image
from src.ingestion.common.pdf import rasterize
from src.ner.common.rules import Extraction, extract, extract_ocr_lines, resolve
from src.ner.common.taxonomy import Section

OCR_DPI = 300


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


def analyze_document(path: Path) -> dict:
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
    extractions: list[Extraction] = []
    if section is not None:
        extractions = extract_ocr_lines(section, layout) if ocr else extract(section, layout)
    return {"file": path.name, "path": str(path), "lang": lang, "section": section.value if section else None,
            "section_detected_by": how, "pages": layout.n_pages, "ocr": ocr,
            "extractions": [e.to_json() for e in extractions], "_extractions": extractions}


def analyze_package(paths: list[Path]) -> dict:
    docs = [analyze_document(Path(p)) for p in paths]
    tep: dict[Section, dict[str, Extraction]] = {}
    duplicates = []
    for d in docs:
        if d["section"] is None:
            continue
        sec = Section(d["section"])
        if sec in tep:
            duplicates.append(d["file"])
            continue
        tep[sec] = resolve(d["_extractions"])
    rooms = [e.value for f, e in tep.get(Section.AR, {}).items() if re.match(r"room\.", f)]
    ocr_sections = frozenset(Section(d["section"]) for d in docs if d["ocr"] and d["section"])
    findings, completeness = check(tep, round(sum(rooms), 2) if rooms else None, ocr_sections)
    langs = {d["lang"] for d in docs}
    for d in docs:
        del d["_extractions"]
    warnings = []
    scans = [d["file"] for d in docs if d["ocr"]]
    if scans:
        warnings.append(f"Без текстового слоя (сканы): {', '.join(scans)}. Таблицы на сканах распознаются "
                        f"ненадёжно: часть проверок пропущена, отсутствие показателей не проверяется.")
    for d in docs:
        if d["section"] is None:
            warnings.append(f"{d['file']}: не удалось определить раздел документа.")
        elif not d["extractions"]:
            warnings.append(f"{d['file']}: не найдено ни одного ТЭП.")
    return {
        "lang": langs.pop() if len(langs) == 1 else "mixed",
        "warnings": warnings,
        "documents": docs,
        "completeness": completeness | {"unrecognised": [d["file"] for d in docs if d["section"] is None],
                                        "duplicates": duplicates},
        "tep": {s.value: {f: e.to_json() for f, e in fields.items()} for s, fields in tep.items()},
        "findings": [asdict(f) for f in findings],
        "summary": {v: sum(f.verdict == v for f in findings) for v in ("MISMATCH", "MISSING", "MATCH")},
    }
