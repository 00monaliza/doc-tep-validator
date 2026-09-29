"""Taxonomy v2 invariants."""

from __future__ import annotations

from src.ner.common.taxonomy import (
    SYNTHETIC_TYPES,
    SYNTHETIC_TYPES_V1,
    TOLERANCES,
    TYPE_LEVEL,
    DiscrepancyType,
    Level,
    ObjectRef,
)


def test_every_type_has_a_level():
    assert set(TYPE_LEVEL) == set(DiscrepancyType)
    assert all(isinstance(lvl, Level) for lvl in TYPE_LEVEL.values())


def test_v1_types_kept_and_synthetic_subset():
    for name in ("AREA_PZ_VS_AR_EXPLICATION", "MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE",
                 "COST_OBJECT_ESTIMATE_VS_SUMMARY", "MISSING_MANDATORY_TEP"):
        assert DiscrepancyType(name) in SYNTHETIC_TYPES_V1
    assert SYNTHETIC_TYPES[:4] == SYNTHETIC_TYPES_V1
    assert len(set(SYNTHETIC_TYPES)) == len(SYNTHETIC_TYPES)
    numeric = {t for t in SYNTHETIC_TYPES if t not in (DiscrepancyType.MISSING_MANDATORY_TEP,
                                                          DiscrepancyType.PARAMETER_CONTRADICTION)}
    assert numeric <= set(TOLERANCES)


def test_object_ref():
    ref = ObjectRef("b1", "Здание 1")
    assert str(ref) == "b1" and ref == ObjectRef("b1", "Здание 1")
