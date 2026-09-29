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


class Level(StrEnum):
    """How a discrepancy is detected, from easiest to hardest for rules."""

    NUMERIC = "numeric"  # two numbers that must agree (with tolerance)
    CATEGORICAL = "categorical"  # a categorical parameter with several values
    LOGICAL = "logical"  # contradicting statements in text
    DOMAIN_RULE = "domain_rule"  # violates engineering knowledge (method, geometry)
    ARTIFACT = "artifact"  # copy-paste traces: wrong labels, foreign references


class DiscrepancyType(StrEnum):
    """Discrepancy types (taxonomy v2).

    The first four come from v1 and are what the synthetic generator injects.
    ``COST_OBJECT_ESTIMATE_VS_SUMMARY`` occurs only in synthetic data: the real
    estimate package seen so far (АВС) had no object estimates, the chain there
    is local estimate → Form 2 → Form 1 (see ``LOCAL_ESTIMATE_VS_SUMMARY``).
    """

    AREA_PZ_VS_AR_EXPLICATION = "AREA_PZ_VS_AR_EXPLICATION"
    MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE = "MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE"
    COST_OBJECT_ESTIMATE_VS_SUMMARY = "COST_OBJECT_ESTIMATE_VS_SUMMARY"  # synthetic only
    MISSING_MANDATORY_TEP = "MISSING_MANDATORY_TEP"
    # v2, derived from real documents
    TEP_CROSS_SECTION_MISMATCH = "TEP_CROSS_SECTION_MISMATCH"  # same TEP of one object differs between sections
    TABLE_TOTAL_MISMATCH = "TABLE_TOTAL_MISMATCH"  # table total != sum of its rows
    VALUE_CROSS_SECTION_MISMATCH = "VALUE_CROSS_SECTION_MISMATCH"  # non-TEP value (e.g. elevation) differs
    PARAMETER_CONTRADICTION = "PARAMETER_CONTRADICTION"  # seismicity, fire resistance, material... differ
    STATEMENT_CONTRADICTION = "STATEMENT_CONTRADICTION"  # contradicting statements in text
    TEP_CALCULATION_METHOD = "TEP_CALCULATION_METHOD"  # value computed by a wrong method
    GEOMETRY_INCONSISTENCY = "GEOMETRY_INCONSISTENCY"  # e.g. building area < area within axes
    COPY_PASTE_LABEL = "COPY_PASTE_LABEL"  # wrong object/table label
    IRRELEVANT_REFERENCE = "IRRELEVANT_REFERENCE"  # normative reference unrelated to the object
    LOCAL_ESTIMATE_VS_SUMMARY = "LOCAL_ESTIMATE_VS_SUMMARY"  # local estimate total != summary estimate row


TYPE_LEVEL: dict[DiscrepancyType, Level] = {
    DiscrepancyType.AREA_PZ_VS_AR_EXPLICATION: Level.NUMERIC,
    DiscrepancyType.MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE: Level.NUMERIC,
    DiscrepancyType.COST_OBJECT_ESTIMATE_VS_SUMMARY: Level.NUMERIC,
    DiscrepancyType.MISSING_MANDATORY_TEP: Level.NUMERIC,
    DiscrepancyType.TEP_CROSS_SECTION_MISMATCH: Level.NUMERIC,
    DiscrepancyType.TABLE_TOTAL_MISMATCH: Level.NUMERIC,
    DiscrepancyType.VALUE_CROSS_SECTION_MISMATCH: Level.NUMERIC,
    DiscrepancyType.LOCAL_ESTIMATE_VS_SUMMARY: Level.NUMERIC,
    DiscrepancyType.PARAMETER_CONTRADICTION: Level.CATEGORICAL,
    DiscrepancyType.STATEMENT_CONTRADICTION: Level.LOGICAL,
    DiscrepancyType.TEP_CALCULATION_METHOD: Level.DOMAIN_RULE,
    DiscrepancyType.GEOMETRY_INCONSISTENCY: Level.DOMAIN_RULE,
    DiscrepancyType.COPY_PASTE_LABEL: Level.ARTIFACT,
    DiscrepancyType.IRRELEVANT_REFERENCE: Level.ARTIFACT,
}

# Types the synthetic generator can inject, in a fixed order (the order drives
# the RNG). Profile v1 injects only the first four; v2 adds the rest, drawn
# from a separate RNG stream so v1 values of a seed stay reproducible.
SYNTHETIC_TYPES_V1: tuple[DiscrepancyType, ...] = (
    DiscrepancyType.AREA_PZ_VS_AR_EXPLICATION,
    DiscrepancyType.MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE,
    DiscrepancyType.COST_OBJECT_ESTIMATE_VS_SUMMARY,
    DiscrepancyType.MISSING_MANDATORY_TEP,
)
SYNTHETIC_TYPES_V2_EXTRA: tuple[DiscrepancyType, ...] = (
    DiscrepancyType.TEP_CROSS_SECTION_MISMATCH,
    DiscrepancyType.TABLE_TOTAL_MISMATCH,
    DiscrepancyType.PARAMETER_CONTRADICTION,
)
SYNTHETIC_TYPES: tuple[DiscrepancyType, ...] = SYNTHETIC_TYPES_V1 + SYNTHETIC_TYPES_V2_EXTRA


@dataclass(frozen=True)
class ObjectRef:
    """One object (building, site) of a project; a package may describe several.

    ``id`` is a stable short key used in ground truth and findings (``abk``,
    ``ceh``, ``b1``); two reserved ids exist: ``site`` (the plot as a whole) and
    ``document`` (findings about the document rather than a building).
    """

    id: str
    name: str = ""

    def __str__(self) -> str:
        return self.id


SITE = ObjectRef("site", "Площадка")
DOCUMENT = ObjectRef("document", "Документ в целом")


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
    DiscrepancyType.TEP_CROSS_SECTION_MISMATCH: Tolerance(rel=0.005, abs=0.1),
    DiscrepancyType.TABLE_TOTAL_MISMATCH: Tolerance(rel=0.0, abs=0.05),  # rows are rounded to 0.01
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
