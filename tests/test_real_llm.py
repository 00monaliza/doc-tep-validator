import pytest

from src.evaluation.real_llm import findings_from_items, guard_real
from src.ingestion.real import Page


def pages():
    return [Page(number=1, text="Общая площадь здания котельной 100 м2", lines=[], tables=[]),
            Page(number=2, text="Сейсмичность 7 баллов", lines=[], tables=[])]


def test_guard_real_refuses_without_flag():
    with pytest.raises(PermissionError, match="--allow-real-llm"):
        guard_real(False)
    guard_real(True)


def test_findings_need_page_and_quote_present_on_that_page():
    base = {"type": "STATEMENT_CONTRADICTION", "field": "", "object": "Котельная"}
    items = [
        base | {"page": 2, "evidence": "Сейсмичность 7"},
        base | {"page": 1, "evidence": "нет такого"},
        base | {"evidence": "Сейсмичность 7"},
    ]
    found, objects = findings_from_items(items, pages())
    assert len(found) == 1 and found[0].refs[0].page == 2
    assert objects[found[0].object] == "Котельная"


def test_findings_level_comes_from_taxonomy():
    items = [{"type": "COPY_PASTE_LABEL", "field": "", "object": "", "page": 1, "evidence": "Общая площадь"}]
    found, _ = findings_from_items(items, pages())
    assert found[0].level.value == "artifact" and found[0].object == "document"
