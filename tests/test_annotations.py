"""Manual annotations of real documents: schema always, quotes only if the PDF is present."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.evaluation.annotations import ANNOTATIONS_DIR, check_quotes, load_annotation, page_texts, source_path
from src.evaluation.schema import Finding

FILES = sorted(ANNOTATIONS_DIR.glob("*.json"))


def test_annotations_exist():
    assert FILES, f"no annotations in {ANNOTATIONS_DIR}"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_schema_parses(path):
    ann = load_annotation(path)
    assert ann.findings


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_quotes_found_on_their_page(path):
    ann = load_annotation(path)
    pdf = source_path(ann)
    if not pdf.exists():
        pytest.skip(f"real document {ann.source_file} is not available (never committed)")
    texts = page_texts(pdf)
    assert len(texts) == ann.pages
    assert check_quotes(ann, texts) == []


def _finding(**kw):
    base = {"id": "X1", "level": "numeric", "type": "TABLE_TOTAL_MISMATCH", "field": "f", "object": "b1",
            "refs": [{"page": 1, "quote": "q"}]}
    return base | kw


def test_level_must_match_type():
    Finding.model_validate(_finding())
    with pytest.raises(ValidationError, match="does not match type"):
        Finding.model_validate(_finding(level="logical"))


def test_unknown_type_and_extra_fields_rejected():
    with pytest.raises(ValidationError):
        Finding.model_validate(_finding(type="NO_SUCH_TYPE"))
    with pytest.raises(ValidationError):
        Finding.model_validate(_finding(refs=[{"page": 1, "quote": "q", "pgae": 2}]))


def test_value_may_be_any_scalar_or_list():
    for v in (1, 2.5, "бетон", False, [314.75, 315.04]):
        f = Finding.model_validate(_finding(refs=[{"page": 1, "quote": "q", "value": v}]))
        assert f.refs[0].value == v
    json.dumps(f.model_dump(mode="json"))


def test_suspected_cause_optional_and_validated():
    assert Finding.model_validate(_finding()).suspected_cause is None
    assert Finding.model_validate(_finding(suspected_cause="copy_paste")).suspected_cause == "copy_paste"
    with pytest.raises(ValidationError):
        Finding.model_validate(_finding(suspected_cause="bad_luck"))


def test_real_annotation_causes():
    ann = load_annotation(ANNOTATIONS_DIR / "real_opz_zhbi2.gt.json")
    causes = {f.id: f.suspected_cause for f in ann.findings}
    assert causes["R6"] == "copy_paste" and causes["R3"] == "calculation_method"
    assert next(f for f in ann.findings if f.id == "R3").type == "TEP_CALCULATION_METHOD"


def test_seismicity_allowed_per_building():
    """Seismicity defaults to the site, but a document may state it for one building."""
    f = Finding.model_validate(_finding(type="PARAMETER_CONTRADICTION", level="categorical", object="b1",
                                        field="seismicity_points",
                                        refs=[{"page": 1, "quote": "q", "object": "b1", "value": 8},
                                              {"page": 2, "quote": "q", "object": "site", "value": 7}]))
    assert {r.object for r in f.refs} == {"b1", "site"}
