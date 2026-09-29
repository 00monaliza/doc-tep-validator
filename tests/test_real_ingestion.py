"""Real-document ingestion: extractability logic on synthetic pages, smoke test on real PDFs if present."""

from __future__ import annotations

import pytest

from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path
from src.evaluation.extractability import measure, summary
from src.evaluation.schema import RealAnnotation
from src.ingestion.real import Page, PageTable, load_pages


def _page(no, text, tables=()):
    return Page(no, text, [], list(tables))


def test_extractability_table_text_none():
    table = PageTable([["Наименование", "Общая площадь", "Строительный объем"], ["Корпус", "1 247,79", "8833,38"]],
                      (0, 100, 500, 200), ["Наименование", "Общая площадь", "Строительный объем"])
    pages = [_page(1, "Корпус 1 247,79 8833,38", [table]), _page(2, "Объем корпуса равен 9100.5 м3")]
    ann = RealAnnotation.model_validate({
        "schema_version": "real-0.1", "document_id": "t", "source_file": "x.pdf", "lang": "ru", "doc_type": "ПЗ",
        "pages": 2, "text_layer": True, "objects": {"b1": "Корпус"}, "findings": [],
        "tep": {"b1": {"total_area_m2": 1247.79, "construction_volume_m3": [8833.38, 9100.5, 777.7], "page": 1}},
    })
    hits = {(h.field, h.expected): h for h in measure(ann, pages)}
    assert hits[("total_area_m2", 1247.79)].where == "table" and hits[("total_area_m2", 1247.79)].column_ok
    assert hits[("construction_volume_m3", 8833.38)].column_ok
    assert hits[("construction_volume_m3", 9100.5)].where == "text"
    assert hits[("construction_volume_m3", 9100.5)].text_pages == [2]
    assert hits[("construction_volume_m3", 777.7)].where == "none"
    assert summary(list(hits.values()))["not_found"] == 1


@pytest.mark.parametrize("path", sorted(ANNOTATIONS_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_load_real_pages(path):
    ann = load_annotation(path)
    pdf = source_path(ann)
    if not pdf.exists():
        pytest.skip(f"real document {ann.source_file} is not available (never committed)")
    pages = load_pages(pdf)
    assert [p.number for p in pages] == list(range(1, ann.pages + 1))
    for p in pages:
        for t in p.tables:
            assert len(t.header) == len(t.rows[0])
            assert all("\n" not in c for row in t.rows for c in row)
