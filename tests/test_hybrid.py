from pathlib import Path

from src.evaluation.systems import HybridSystem

AREA = "AREA_PZ_VS_AR_EXPLICATION"
STMT = "STATEMENT_CONTRADICTION"
COPY = "COPY_PASTE_LABEL"


class StubRules:
    name = "S1"

    def detect(self, paths, lang):
        return {(AREA, "")}


class StubLLM:
    def __init__(self, items):
        self.items = items

    def detect_items(self, paths):
        return self.items


def test_hybrid_takes_rules_plus_llm_logical_and_artifact_only():
    llm = StubLLM([{"type": STMT, "field": ""}, {"type": COPY, "field": "f"}, {"type": "TABLE_TOTAL_MISMATCH",
                                                                               "field": "t"}])
    got = HybridSystem(StubRules(), llm).detect([Path("x.pdf")], "ru")
    assert got == {(AREA, ""), (STMT, ""), (COPY, "f")}


def test_hybrid_ignores_llm_numeric_claims_even_when_rules_found_nothing():
    class NoRules(StubRules):
        def detect(self, paths, lang):
            return set()

    llm = StubLLM([{"type": AREA, "field": "total_area_m2"}])
    assert HybridSystem(NoRules(), llm).detect([Path("x.pdf")], "ru") == set()


def test_hybrid_name():
    assert HybridSystem(StubRules(), StubLLM([])).name == "H1"


def test_hybrid_null_field_becomes_empty_slot():
    llm = StubLLM([{"type": STMT, "field": None}])
    assert (STMT, "") in HybridSystem(StubRules(), llm).detect([Path("x.pdf")], "ru")
