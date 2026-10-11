"""Profile v4: what the ПЗ of v2 does not state yet — site relief, building elevation 0.000, storey and clear
heights, blind area and roof — and four more discrepancy types. Drawn from its own RNG stream on top of a v2
plan, which stays untouched."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from src.ner.common.taxonomy import DiscrepancyType, Verdict
from src.synthesis.values import PzPlan, mention_key

BLIND_MATERIALS = ("concrete", "asphalt")
BLIND_WIDTHS_MM = (800, 1000, 1200, 1500)
ROOFS = ("membrane", "bitumen", "profiled")
ELEVATION_SLACK_M = (0.15, 0.6)  # building 0.000 above the relief range
ELEVATION_JUMP_M = (20.0, 200.0)  # an elevation copied from another project


@dataclass
class V4Plan:
    values: dict[str, float | str]
    labels: dict[str, str]  # building id -> id of the building named in its ТЭП table ("" = its own)
    discrepancies: list[dict] = field(default_factory=list)
    consistent_checks: list[dict] = field(default_factory=list)

    def refresh(self) -> None:
        """Copy values written during rendering (table labels) into the ground-truth refs."""
        for rec in self.discrepancies + self.consistent_checks:
            for ref in rec["refs"]:
                if ref["mention"] in self.values:
                    ref["value"] = self.values[ref["mention"]]


def blind_value(material: str, width_mm: int) -> str:
    return f"{material}, {width_mm} мм"


def plan_v4(rng: random.Random, plan: PzPlan, floor_height_b1: float, inject: set[DiscrepancyType]) -> V4Plan:
    values: dict[str, float | str] = {}
    lo = round(rng.uniform(200, 900), 2)
    hi = round(lo + rng.uniform(0.3, 3.0), 2)
    values[mention_key("site", "relief", "relief_min_m")] = lo
    values[mention_key("site", "relief", "relief_max_m")] = hi
    blind_all = (rng.choice(BLIND_MATERIALS), rng.choice(BLIND_WIDTHS_MM))
    roof_all = rng.choice(ROOFS)
    values[mention_key("all", "landscaping", "blind_area")] = blind_value(*blind_all)
    values[mention_key("all", "landscaping", "roof")] = roof_all
    for b in plan.buildings:
        values[mention_key(b.id, "object_section", "absolute_elevation_m")] = round(
            rng.uniform(lo, hi) + rng.uniform(*ELEVATION_SLACK_M), 2)
        s, v, n = b.tep["building_area_m2"], b.tep["construction_volume_m3"], b.tep["floors"]
        if b.primary or not (s and v and n):
            fh = floor_height_b1
        else:
            fh = round((v / s - 0.5) / n, 2)  # inverse of values._aux_building
        values[mention_key(b.id, "object_section", "floor_height_m")] = fh
        values[mention_key(b.id, "object_section", "clear_height_m")] = round(fh - rng.uniform(0.3, 0.5), 2)
        values[mention_key(b.id, "object_section", "blind_area")] = blind_value(*blind_all)
        values[mention_key(b.id, "object_section", "roof")] = roof_all
        values[mention_key(b.id, "object_table", "object_label")] = ""  # the written name, set when rendering
    labels = {b.id: "" for b in plan.buildings}

    by_id = {b.id: b for b in plan.buildings}
    calc_target = None
    if DiscrepancyType.TEP_CALCULATION_METHOD in inject:
        ones = [b for b in plan.buildings if b.tep["floors"] == 1 and b.tep["building_area_m2"]
                and b.tep["construction_volume_m3"]]
        if ones:
            b = rng.choice(ones)
            calc_target = b.id
            values[mention_key(b.id, "object_section", "clear_height_m")] = round(
                b.tep["construction_volume_m3"] / b.tep["building_area_m2"], 2)  # V = S x clear height
    elevation_target = None
    if DiscrepancyType.VALUE_CROSS_SECTION_MISMATCH in inject:
        b = rng.choice(plan.buildings)
        elevation_target = b.id
        key = mention_key(b.id, "object_section", "absolute_elevation_m")
        values[key] = round(float(values[key]) + rng.choice((-1, 1)) * rng.uniform(*ELEVATION_JUMP_M), 2)
    label_target = None
    if DiscrepancyType.COPY_PASTE_LABEL in inject and len(plan.buildings) >= 2:
        b, other = rng.sample(plan.buildings, 2)
        label_target, labels[b.id] = b.id, other.id
    param_target = None
    if DiscrepancyType.PARAMETER_CONTRADICTION in inject:
        b = rng.choice(plan.buildings)
        param = rng.choice(("blind_area", "roof"))
        param_target = (b.id, param)
        key = mention_key(b.id, "object_section", param)
        if param == "roof":
            values[key] = rng.choice([r for r in ROOFS if r != roof_all])
        elif rng.random() < 0.5:
            values[key] = blind_value(rng.choice([m for m in BLIND_MATERIALS if m != blind_all[0]]), blind_all[1])
        else:
            values[key] = blind_value(blind_all[0], rng.choice([w for w in BLIND_WIDTHS_MM if w != blind_all[1]]))

    out = V4Plan(values, labels)

    def ref(obj: str, place: str, fld: str) -> dict:
        key = mention_key(obj, place, fld)
        value = values[key] if key in values else plan.values[key]  # v2 statements (ТЭП tables) are referenced too
        return {"object": obj, "section": "PZ", "field": fld, "place": place, "value": value, "mention": key}

    def record(dtype: DiscrepancyType, obj: str, fld: str, refs: list[dict], mismatch: bool) -> None:
        rec = {"type": dtype.value, "object": obj, "field": fld, "refs": refs,
               "expected_verdict": (Verdict.MISMATCH if mismatch else Verdict.MATCH).value}
        (out.discrepancies if mismatch else out.consistent_checks).append(rec)

    relief = [ref("site", "relief", "relief_min_m"), ref("site", "relief", "relief_max_m")]
    for b in plan.buildings:
        record(DiscrepancyType.VALUE_CROSS_SECTION_MISMATCH, "site", "absolute_elevation_m",
               [ref(b.id, "object_section", "absolute_elevation_m")] + relief, b.id == elevation_target)
        if by_id[b.id].tep["construction_volume_m3"]:
            record(DiscrepancyType.TEP_CALCULATION_METHOD, b.id, "construction_volume_m3",
                   [ref(b.id, "object_table", "construction_volume_m3"), ref(b.id, "object_section", "clear_height_m")],
                   b.id == calc_target)
        if b.id == label_target:
            record(DiscrepancyType.COPY_PASTE_LABEL, b.id, "object_label",
                   [ref(b.id, "object_table", "object_label")], True)
        for param in ("blind_area", "roof"):
            record(DiscrepancyType.PARAMETER_CONTRADICTION, "all", param,
                   [ref(b.id, "object_section", param), ref("all", "landscaping", param)],
                   param_target == (b.id, param))
    return out
