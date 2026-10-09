"""S1 must stay the system measured in E2/E3 (tag protocol-v1); S2 is the service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.evaluation.systems import RulesSystem, RulesSystemV1
from src.synthesis.generator import generate_set

REF = json.loads((Path(__file__).parent / "data" / "s1_protocol_v1_slots.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", sorted(REF))
def test_s1_matches_protocol_v1(tmp_path, key):
    lang, seed = key.split("_")
    d = generate_set(lang, int(seed), tmp_path, scans=False, profile="v2")
    slots = RulesSystem().detect(sorted((d / "text").glob("*.pdf")), lang)
    assert sorted(list(s) for s in slots) == REF[key]


def test_s2_is_named_and_uses_v1():
    assert (RulesSystem.name, RulesSystem.detectors) == ("S1", "v0")
    assert (RulesSystemV1.name, RulesSystemV1.detectors) == ("S2", "v1")
