"""Language-independent taxonomy of sections, TEP fields and discrepancy types.

Everything here is keyed by stable ASCII identifiers; RU/KZ surface forms live
in the synthesis lexicons and (later) in the per-language NER modules. Ground
truth JSON, the cross-validation module and evaluation all speak these ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Section(StrEnum):
    PZ = "PZ"  # Пояснительная записка / Түсіндірме жазба
    AR = "AR"  # Архитектурные решения (текстовая часть) / Сәулет шешімдері
    KR = "KR"  # Конструктивные решения (текстовая часть) / Конструктивтік шешімдер
    SMETA = "SMETA"  # Сметная документация (ЛС + ОС + ССР) / Сметалық құжаттама


class DiscrepancyType(StrEnum):
    AREA_PZ_VS_AR_EXPLICATION = "AREA_PZ_VS_AR_EXPLICATION"
    MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE = "MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE"
    COST_OBJECT_ESTIMATE_VS_SUMMARY = "COST_OBJECT_ESTIMATE_VS_SUMMARY"
    MISSING_MANDATORY_TEP = "MISSING_MANDATORY_TEP"


class Verdict(StrEnum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    MISSING = "MISSING"


@dataclass(frozen=True)
class Tolerance:
    """A pair of values is a MATCH if |a-b| <= max(abs_tol, rel_tol*max(|a|,|b|))."""

    rel: float
    abs: float

    def matches(self, a: float, b: float) -> bool:
        return abs(a - b) <= max(self.abs, self.rel * max(abs(a), abs(b)))


# Tolerances the cross-validator is expected to use; the generator guarantees
# that every injected MISMATCH lies well outside them.
TOLERANCES: dict[DiscrepancyType, Tolerance] = {
    DiscrepancyType.AREA_PZ_VS_AR_EXPLICATION: Tolerance(rel=0.005, abs=0.1),
    DiscrepancyType.MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE: Tolerance(rel=0.01, abs=0.01),
    DiscrepancyType.COST_OBJECT_ESTIMATE_VS_SUMMARY: Tolerance(rel=0.0, abs=0.001),
}


@dataclass(frozen=True)
class TepField:
    id: str
    unit: str  # canonical unit
    kind: str  # area | volume | mass | count | cost | duration


# Canonical TEP fields. Section-specific keys in the ground truth reuse these
# ids, optionally prefixed (e.g. "local_qty.concrete_b25_foundation_m3").
TEP_FIELDS: dict[str, TepField] = {f.id: f for f in [
    TepField("floors", "floor", "count"),
    TepField("building_area_m2", "m2", "area"),
    TepField("total_area_m2", "m2", "area"),
    TepField("construction_volume_m3", "m3", "volume"),
    TepField("underground_volume_m3", "m3", "volume"),
    TepField("estimated_cost_ktg", "kKZT", "cost"),
    TepField("construction_duration_months", "month", "duration"),
    TepField("explication_total_area_m2", "m2", "area"),
    TepField("concrete_b25_foundation_m3", "m3", "volume"),
    TepField("concrete_b30_frame_m3", "m3", "volume"),
    TepField("rebar_a500c_t", "t", "mass"),
    TepField("concrete_total_m3", "m3", "volume"),
    TepField("brick_masonry_m3", "m3", "volume"),
    TepField("steel_structures_t", "t", "mass"),
]}

MATERIALS: tuple[str, ...] = (
    "concrete_b25_foundation_m3",
    "concrete_b30_frame_m3",
    "rebar_a500c_t",
    "brick_masonry_m3",
    "steel_structures_t",
)

# (section, field) pairs whose absence is a MISSING_MANDATORY_TEP finding, with
# the section/field where the same quantity can be found for reference.
MANDATORY_TEP: dict[tuple[Section, str], tuple[Section, str]] = {
    (Section.PZ, "building_area_m2"): (Section.AR, "building_area_m2"),
    (Section.PZ, "construction_volume_m3"): (Section.AR, "construction_volume_m3"),
    (Section.PZ, "estimated_cost_ktg"): (Section.SMETA, "ssr.total_ktg"),
    (Section.KR, "rebar_a500c_t"): (Section.SMETA, "local_qty.rebar_a500c_t"),
    (Section.KR, "steel_structures_t"): (Section.SMETA, "local_qty.steel_structures_t"),
}
