import json

import pytest

from src.evaluation.gap import MISS_CAUSES, choose_scenario, load_misses, summarize_misses


def test_choose_scenario_threshold():
    assert choose_scenario(0) == "B" and choose_scenario(4) == "B"
    assert choose_scenario(5) == "A" and choose_scenario(12) == "A"


def test_summarize_misses_counts_causes_and_flags_unlabeled():
    misses = {"F1": {"cause": "no_rule", "note": ""}, "F2": {"cause": "table_format", "note": "x"}}
    got = summarize_misses(["F1", "F2", "F3", "F1"], misses)
    assert got == {"no_rule": 2, "table_format": 1, "unlabeled": 1}


def test_load_misses_validates_causes(tmp_path):
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"F1": {"cause": "no_rule", "note": "n"}}), encoding="utf-8")
    assert load_misses(ok)["F1"]["cause"] == "no_rule"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"F1": {"cause": "nonsense", "note": ""}}), encoding="utf-8")
    with pytest.raises(ValueError, match="nonsense"):
        load_misses(bad)


def test_load_misses_missing_file_is_empty(tmp_path):
    assert load_misses(tmp_path / "nope.json") == {}


def test_miss_causes_contains_expected_groups():
    assert {"table_format", "object_resolution", "terminology", "language", "ocr", "no_rule"} <= set(MISS_CAUSES)
