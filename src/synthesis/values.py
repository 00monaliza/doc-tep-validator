"""Language-independent generation of TEP values and injected discrepancies.

Order of generation guarantees internal consistency of every section:

    rooms ─► AR explication total ─► PZ total area            (D1 perturbs PZ)
    footprint/volume ─► PZ, AR
    materials ─► KR ─► local estimate quantities ─► costs      (D2 perturbs LS qty)
    local total ─► object estimate ─► summary estimate ch.2    (D3 perturbs SSR ch.2)
    summary total ─► PZ estimated cost
    D4 blanks one mandatory TEP in one section.

Only the injected fields disagree across sections; all totals inside a section
are recomputed from that section's own (possibly perturbed) numbers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from src.ner.common.taxonomy import (
    MANDATORY_TEP,
    MATERIALS,
    TOLERANCES,
    DiscrepancyType,
    Section,
    Verdict,
)

# ------------------------------------------------------------------ catalog
ROOM_AREA: dict[str, tuple[float, float]] = {
    "vestibule": (40, 90), "corridor": (30, 120), "stair": (18, 26), "wc": (6, 18),
    "storage": (6, 15), "tech": (10, 30), "classroom": (50, 66), "lab": (66, 80),
    "sportshall": (288, 420), "assembly": (200, 320), "canteen": (150, 280), "kitchen": (60, 120),
    "library": (60, 120), "teachers": (30, 50), "medical": (14, 24), "group": (50, 60),
    "bedroom": (46, 55), "music_hall": (75, 100), "laundry": (15, 25), "office": (15, 36),
    "meeting": (40, 90), "reception": (18, 30), "archive": (20, 40), "server": (12, 24),
    "doctor_office": (12, 20), "procedure": (15, 24), "registry": (30, 60), "waiting": (30, 70),
    "xray": (30, 45), "lab_clin": (24, 40),
}
ROOM_CATEGORY = {"storage": "В4", "tech": "Д", "archive": "В3", "server": "В4", "laundry": "Д"}

COMMON_FLOOR = ["corridor", "stair", "stair", "wc", "wc"]


@dataclass(frozen=True)
class BuildingType:
    capacity: tuple[int, int, int]  # min, max, step
    floors: tuple[int, int]
    fire_class: str
    first_floor: tuple[str, ...]
    upper_floor: tuple[str, ...]
    filler: str  # repeated room type
    filler_count: tuple[int, int]


BUILDING_TYPES: dict[str, BuildingType] = {
    "school": BuildingType((300, 1200, 50), (2, 4), "Ф4.1",
                           ("vestibule", "canteen", "kitchen", "sportshall", "medical", "storage", "tech"),
                           ("library", "teachers", "lab", "storage"), "classroom", (4, 8)),
    "kindergarten": BuildingType((120, 320, 20), (2, 3), "Ф1.1",
                                 ("vestibule", "kitchen", "medical", "laundry", "music_hall", "tech"),
                                 ("storage",), "group", (2, 4)),
    "admin": BuildingType((50, 200, 10), (2, 4), "Ф4.3",
                          ("vestibule", "reception", "meeting", "archive", "tech"),
                          ("meeting", "server", "storage"), "office", (6, 10)),
    "polyclinic": BuildingType((150, 500, 25), (2, 4), "Ф3.4",
                               ("vestibule", "registry", "waiting", "xray", "lab_clin", "tech"),
                               ("waiting", "procedure", "storage"), "doctor_office", (5, 9)),
}

UNIT_PRICE_TG: dict[str, tuple[float, float]] = {
    "concrete_b25_foundation_m3": (88_000, 102_000),
    "concrete_b30_frame_m3": (105_000, 128_000),
    "rebar_a500c_t": (470_000, 560_000),
    "brick_masonry_m3": (58_000, 72_000),
    "steel_structures_t": (690_000, 860_000),
}
MATERIAL_DECIMALS = {m: (3 if m.endswith("_t") else 2) for m in MATERIALS}

# Object estimate: local estimate numbers and cost per m² of total area (kKZT/m²),
# except 02-01-01 which is taken from the generated local estimate.
OBJECT_ESTIMATE_ROWS: dict[str, tuple[str, tuple[float, float] | None]] = {
    "02-01-01": ("rc_masonry", None),
    "02-01-02": ("finishing", (90, 130)),
    "02-01-03": ("hvac", (30, 45)),
    "02-01-04": ("water", (18, 28)),
    "02-01-05": ("electric", (25, 38)),
    "02-01-06": ("low_current", (10, 18)),
}
OBJECT_ESTIMATE_NO = "02-01"

# Magnitude of injected discrepancies (relative, both signs) — far outside tolerances.
PERTURBATION = {
    DiscrepancyType.AREA_PZ_VS_AR_EXPLICATION: (0.015, 0.12),
    DiscrepancyType.MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE: (0.05, 0.25),
    DiscrepancyType.COST_OBJECT_ESTIMATE_VS_SUMMARY: (0.005, 0.08),
}


@dataclass
class Room:
    floor: int
    number: str
    kind: str
    area_m2: float
    category: str


@dataclass
class SetValues:
    building_type: str
    capacity: int
    fire_class: str
    floors: int
    floor_height_m: float
    has_basement: bool
    axes_m: tuple[float, float]
    foundation_thickness_mm: int
    duration_months: int
    rooms: list[Room]
    # Per-section flat TEP maps (value None == deliberately absent from the document).
    tep: dict[Section, dict[str, float | int | None]] = field(default_factory=dict)
    discrepancies: list[dict] = field(default_factory=list)
    consistent_checks: list[dict] = field(default_factory=list)


def _perturb(rng: random.Random, value: float, lo: float, hi: float, decimals: int) -> float:
    while True:
        new = round(value * (1 + rng.choice((-1, 1)) * rng.uniform(lo, hi)), decimals)
        if new != value:
            return new


def _rooms(rng: random.Random, bt: BuildingType, floors: int) -> list[Room]:
    rooms: list[Room] = []
    for floor in range(1, floors + 1):
        kinds = list(bt.first_floor if floor == 1 else bt.upper_floor)
        kinds += [bt.filler] * rng.randint(*bt.filler_count) + COMMON_FLOOR
        if floor > 1 and bt.filler in ("classroom", "group"):
            kinds += ["storage"]
        for i, kind in enumerate(kinds, start=1):
            lo, hi = ROOM_AREA[kind]
            rooms.append(Room(floor, f"{floor}{i:02d}", kind, round(rng.uniform(lo, hi), 2),
                              ROOM_CATEGORY.get(kind, "—")))
    return rooms


def generate_values(rng: random.Random, inject: set[DiscrepancyType]) -> SetValues:
    btype = rng.choice(sorted(BUILDING_TYPES))
    bt = BUILDING_TYPES[btype]
    floors = rng.randint(*bt.floors)
    rooms = _rooms(rng, bt, floors)

    explication_total = round(sum(r.area_m2 for r in rooms), 2)
    largest_floor = max(sum(r.area_m2 for r in rooms if r.floor == f) for f in range(1, floors + 1))
    building_area = round(largest_floor * rng.uniform(1.10, 1.16), 2)
    floor_height = rng.choice((3.3, 3.6))
    has_basement = rng.random() < 0.5
    underground = round(building_area * 2.8, 2) if has_basement else None
    construction_volume = round(building_area * (floors * floor_height + 1.2) + (underground or 0), 2)
    ratio = rng.uniform(1.6, 2.6)
    axis_b = round((building_area / ratio) ** 0.5, 1)
    axes = (round(building_area / axis_b, 1), axis_b)
    thickness_mm = rng.choice((600, 700, 800, 900, 1000))

    # --- KR materials (true values)
    foundation = building_area * thickness_mm / 1000 * 1.05
    frame = explication_total * rng.uniform(0.20, 0.26)
    materials = {
        "concrete_b25_foundation_m3": foundation,
        "concrete_b30_frame_m3": frame,
        "rebar_a500c_t": foundation * rng.uniform(0.09, 0.11) + frame * rng.uniform(0.12, 0.15),
        "brick_masonry_m3": explication_total * rng.uniform(0.10, 0.16),
        "steel_structures_t": explication_total * rng.uniform(0.005, 0.012),
    }
    materials = {m: round(v, MATERIAL_DECIMALS[m]) for m, v in materials.items()}

    # --- D4 is decided first so the other injections avoid the blanked field.
    missing: tuple[Section, str] | None = None
    if DiscrepancyType.MISSING_MANDATORY_TEP in inject:
        missing = rng.choice(sorted(MANDATORY_TEP))

    kr: dict[str, float | int | None] = dict(materials)
    kr["concrete_total_m3"] = round(materials["concrete_b25_foundation_m3"] + materials["concrete_b30_frame_m3"], 2)
    local_qty = dict(materials)
    discrepancies: list[dict] = []
    checks: list[dict] = []

    d2_material = None
    if DiscrepancyType.MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE in inject:
        candidates = [m for m in MATERIALS if missing != (Section.KR, m)]
        d2_material = rng.choice(candidates)
        lo, hi = PERTURBATION[DiscrepancyType.MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE]
        local_qty[d2_material] = _perturb(rng, materials[d2_material], lo, hi, MATERIAL_DECIMALS[d2_material])

    # --- local estimate 02-01-01
    smeta: dict[str, float | int | None] = {}
    direct = 0.0
    for m in MATERIALS:
        price = round(rng.uniform(*UNIT_PRICE_TG[m]), 2)
        cost = round(local_qty[m] * price, 2)
        smeta[f"local_qty.{m}"] = local_qty[m]
        smeta[f"local_unit_price_tg.{m}"] = price
        smeta[f"local_cost_tg.{m}"] = cost
        direct += cost
    overhead_pct = rng.choice((8.5, 9.0, 10.0, 11.5, 12.0))
    profit_pct = 8.0
    direct = round(direct, 2)
    overhead = round(direct * overhead_pct / 100, 2)
    profit = round((direct + overhead) * profit_pct / 100, 2)
    local_total = round(direct + overhead + profit, 2)
    smeta |= {"local.direct_tg": direct, "local.overhead_pct": overhead_pct, "local.overhead_tg": overhead,
              "local.profit_pct": profit_pct, "local.profit_tg": profit, "local.total_tg": local_total}

    # --- object estimate 02-01 (kKZT)
    os_total = 0.0
    for ls_no, (_, per_m2) in OBJECT_ESTIMATE_ROWS.items():
        cost = round(local_total / 1000, 3) if per_m2 is None else round(explication_total * rng.uniform(*per_m2), 3)
        smeta[f"os.ls_{ls_no}_ktg"] = cost
        os_total += cost
    os_total = round(os_total, 3)
    smeta["os.total_ktg"] = os_total

    # --- summary estimate (ССР), kKZT
    ch2 = os_total
    if DiscrepancyType.COST_OBJECT_ESTIMATE_VS_SUMMARY in inject:
        lo, hi = PERTURBATION[DiscrepancyType.COST_OBJECT_ESTIMATE_VS_SUMMARY]
        ch2 = _perturb(rng, os_total, lo, hi, 3)
    ch1 = round(ch2 * rng.uniform(0.01, 0.03), 3)
    ch7 = round(ch2 * rng.uniform(0.03, 0.07), 3)
    ch8 = round((ch1 + ch2 + ch7) * rng.uniform(0.015, 0.025), 3)
    ch9 = round((ch1 + ch2 + ch7 + ch8) * rng.uniform(0.02, 0.04), 3)
    ch12 = round((ch1 + ch2 + ch7 + ch8 + ch9) * rng.uniform(0.04, 0.06), 3)
    subtotal = round(ch1 + ch2 + ch7 + ch8 + ch9 + ch12, 3)
    reserve = round(subtotal * 0.02, 3)
    with_reserve = round(subtotal + reserve, 3)
    vat = round(with_reserve * 0.12, 3)
    ssr_total = round(with_reserve + vat, 3)
    smeta |= {"ssr.ch1_ktg": ch1, f"ssr.ch2.os_{OBJECT_ESTIMATE_NO}_ktg": ch2, "ssr.ch7_ktg": ch7,
              "ssr.ch8_ktg": ch8, "ssr.ch9_ktg": ch9, "ssr.ch12_ktg": ch12, "ssr.subtotal_ktg": subtotal,
              "ssr.reserve_ktg": reserve, "ssr.with_reserve_ktg": with_reserve, "ssr.vat_ktg": vat,
              "ssr.total_ktg": ssr_total}

    # --- PZ and AR
    pz_total_area = explication_total
    if DiscrepancyType.AREA_PZ_VS_AR_EXPLICATION in inject:
        lo, hi = PERTURBATION[DiscrepancyType.AREA_PZ_VS_AR_EXPLICATION]
        pz_total_area = _perturb(rng, explication_total, lo, hi, 2)
    pz: dict[str, float | int | None] = {
        "floors": floors, "building_area_m2": building_area, "total_area_m2": pz_total_area,
        "construction_volume_m3": construction_volume, "underground_volume_m3": underground,
        "estimated_cost_ktg": ssr_total, "construction_duration_months": rng.randint(10, 24),
    }
    ar: dict[str, float | int | None] = {
        "floors": floors, "explication_total_area_m2": explication_total,
        "building_area_m2": building_area, "construction_volume_m3": construction_volume,
    }
    tep = {Section.PZ: pz, Section.AR: ar, Section.KR: kr, Section.SMETA: smeta}
    if missing:
        tep[missing[0]][missing[1]] = None

    # --- ground-truth records
    def ref(section: Section, fld: str, **extra) -> dict:
        return {"section": section.value, "field": fld, "value": tep[section][fld]} | extra

    def comparison(dtype: DiscrepancyType, fld: str, a: dict, b: dict) -> dict:
        va, vb = a["value"], b["value"]
        tol = TOLERANCES[dtype]
        verdict = Verdict.MATCH if tol.matches(va, vb) else Verdict.MISMATCH
        return {"type": dtype.value, "field": fld, "refs": [a, b],
                "delta_abs": round(va - vb, 3), "delta_rel": round((va - vb) / vb, 5),
                "tolerance": {"rel": tol.rel, "abs": tol.abs}, "expected_verdict": verdict.value}

    rec = comparison(DiscrepancyType.AREA_PZ_VS_AR_EXPLICATION, "total_area_m2",
                     ref(Section.PZ, "total_area_m2"),
                     ref(Section.AR, "explication_total_area_m2", derived_from="sum(AR.rooms[].area_m2)"))
    (discrepancies if rec["expected_verdict"] == Verdict.MISMATCH else checks).append(rec)

    for m in MATERIALS:
        if kr[m] is None:
            continue
        rec = comparison(DiscrepancyType.MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE, m,
                         ref(Section.KR, m), ref(Section.SMETA, f"local_qty.{m}"))
        (discrepancies if rec["expected_verdict"] == Verdict.MISMATCH else checks).append(rec)

    rec = comparison(DiscrepancyType.COST_OBJECT_ESTIMATE_VS_SUMMARY, "object_estimate_total_ktg",
                     ref(Section.SMETA, "os.total_ktg"),
                     ref(Section.SMETA, f"ssr.ch2.os_{OBJECT_ESTIMATE_NO}_ktg"))
    (discrepancies if rec["expected_verdict"] == Verdict.MISMATCH else checks).append(rec)

    if missing:
        ref_section, ref_field = MANDATORY_TEP[missing]
        discrepancies.append({
            "type": DiscrepancyType.MISSING_MANDATORY_TEP.value, "field": missing[1],
            "refs": [ref(missing[0], missing[1], present=False), ref(ref_section, ref_field, present=True)],
            "missing_in": missing[0].value, "expected_verdict": Verdict.MISSING.value,
        })

    for i, d in enumerate(discrepancies, start=1):
        d["id"] = f"D{i}"
    for i, c in enumerate(checks, start=1):
        c["id"] = f"C{i}"

    return SetValues(
        building_type=btype, capacity=rng.randrange(bt.capacity[0], bt.capacity[1] + 1, bt.capacity[2]),
        fire_class=bt.fire_class, floors=floors, floor_height_m=floor_height, has_basement=has_basement,
        axes_m=axes, foundation_thickness_mm=thickness_mm, duration_months=int(pz["construction_duration_months"]),
        rooms=rooms, tep=tep, discrepancies=discrepancies, consistent_checks=checks,
    )


# ================================================================== profile v2
# Several buildings in one package, and TEP/parameters repeated across sections
# of the explanatory note (ПЗ). Only the ПЗ describes the extra buildings; AR,
# KR and the estimate stay about the primary building b1.

AUX_KINDS: dict[str, tuple[tuple[int, int], tuple[float, float], tuple[float, float], tuple[float, float]]] = {
    # floors, axis A (m), axis B (m), storey height (m)
    "boiler": ((1, 1), (9, 18), (6, 12), (4.2, 6.0)),
    "warehouse": ((1, 1), (12, 36), (9, 18), (4.8, 7.2)),
    "checkpoint": ((1, 1), (4.5, 9), (3, 6), (3.0, 3.3)),
    "garage": ((1, 1), (12, 24), (6, 12), (3.6, 4.8)),
    "substation": ((1, 1), (6, 12), (4.5, 6), (3.6, 4.2)),
    "utility": ((1, 2), (9, 18), (6, 12), (3.0, 3.6)),
}
OBJECT_FIELDS = ("floors", "building_area_m2", "total_area_m2", "construction_volume_m3")
SUMMARY_FIELDS = ("building_area_m2", "total_area_m2", "construction_volume_m3")
TEXT_FIELDS = ("construction_volume_m3", "total_area_m2")
FIRE_GRADES = ("I", "II", "III", "IV")
SEISMIC_POINTS = (6, 7, 8, 9)


def mention_key(obj: str, place: str, fld: str) -> str:
    """Anchor key of one statement of a value: object : place in the ПЗ : field."""
    return f"{obj}:{place}:{fld}"


@dataclass
class Building:
    id: str
    kind: str  # building type for b1, AUX_KINDS key otherwise
    primary: bool
    tep: dict[str, float | int | None]  # OBJECT_FIELDS
    axes_m: tuple[float, float] | None
    fire_resistance: str
    responsibility: str


@dataclass
class PzPlan:
    buildings: list[Building]
    seismicity: int
    values: dict[str, float | int | str]  # mention_key -> value as written in the ПЗ
    decimals: dict[str, int]  # mention_key -> decimals used when writing (text mentions)
    text_mentions: list[tuple[str, str]]  # (object, field) stated in the engineering section
    summary_fields: tuple[str, ...]
    discrepancies: list[dict] = field(default_factory=list)
    consistent_checks: list[dict] = field(default_factory=list)


def _aux_building(rng: random.Random, bid: str, kind: str) -> Building:
    floors_rng, a_rng, b_rng, h_rng = AUX_KINDS[kind]
    floors = rng.randint(*floors_rng)
    a, b = round(rng.uniform(*a_rng) * 2) / 2, round(rng.uniform(*b_rng) * 2) / 2
    building_area = round(a * b * rng.uniform(1.02, 1.07), 2)  # outer contour > area within axes
    total_area = round(building_area * floors * rng.uniform(0.80, 0.90), 2)
    volume = round(building_area * (floors * rng.uniform(*h_rng) + 0.5), 2)
    return Building(bid, kind, False,
                    {"floors": floors, "building_area_m2": building_area, "total_area_m2": total_area,
                     "construction_volume_m3": volume},
                    (a, b), rng.choice(FIRE_GRADES[1:]), rng.choice(("II", "III")))


def _near_tolerance(rng: random.Random, value: float, tol_rel: float, tol_abs: float) -> float:
    """A value 1.2–3 tolerances away from `value` (a borderline MISMATCH)."""
    tol = max(tol_abs, tol_rel * abs(value))
    return round(value + rng.choice((-1, 1)) * rng.uniform(1.2, 3.0) * tol, 2)


def plan_objects(rng: random.Random, v: SetValues, inject: set[DiscrepancyType]) -> PzPlan:
    pz = v.tep[Section.PZ]
    b1 = Building("b1", v.building_type, True, {f: pz[f] for f in OBJECT_FIELDS}, None, "II", "II")
    n_aux = rng.choice((0, 1, 1, 2))
    buildings = [b1] + [_aux_building(rng, f"b{i}", kind)
                        for i, kind in enumerate(rng.sample(sorted(AUX_KINDS), n_aux), start=2)]
    seismicity = rng.choice(SEISMIC_POINTS)
    # a TEP deliberately missing from the ПЗ (D4) stays missing everywhere in the ПЗ
    summary_fields = tuple(f for f in SUMMARY_FIELDS if b1.tep[f] is not None)

    values: dict[str, float | int | str] = {}
    for b in buildings:
        for f in OBJECT_FIELDS:
            if b.tep[f] is not None:
                values[mention_key(b.id, "object_table", f)] = b.tep[f]
        for f in summary_fields:
            values[mention_key(b.id, "summary_table", f)] = b.tep[f]
        values[mention_key(b.id, "object_section", "seismicity_points")] = seismicity
        values[mention_key(b.id, "object_section", "fire_resistance")] = b.fire_resistance
        values[mention_key(b.id, "fire_section", "fire_resistance")] = b.fire_resistance
    for f in summary_fields:
        values[mention_key("all", "summary_total", f)] = round(sum(b.tep[f] for b in buildings), 2)
    values[mention_key("site", "site_general", "seismicity_points")] = seismicity

    # engineering-section sentences repeating a TEP ("объём здания ... равен ... м³"),
    # sometimes rounded differently from the table (still a MATCH)
    tol = TOLERANCES[DiscrepancyType.TEP_CROSS_SECTION_MISMATCH]
    text_mentions, decimals = [], {}
    for b in buildings:
        fields = [f for f in TEXT_FIELDS if b.tep[f] is not None]
        if fields and rng.random() < 0.6:
            text_mentions.append((b.id, rng.choice(fields)))
    if DiscrepancyType.TEP_CROSS_SECTION_MISMATCH in inject and not text_mentions:
        b = rng.choice([b for b in buildings if any(b.tep[f] is not None for f in TEXT_FIELDS)])
        text_mentions.append((b.id, rng.choice([f for f in TEXT_FIELDS if b.tep[f] is not None])))
    by_id = {b.id: b for b in buildings}
    for obj, f in text_mentions:
        value = float(by_id[obj].tep[f])
        options = [2, 2, 1] + ([0, 0] if 0.5 / value < tol.rel / 2 else [])
        d = rng.choice(options)
        key = mention_key(obj, "engineering_text", f)
        values[key], decimals[key] = round(value, d), d

    discrepancies: list[dict] = []
    if DiscrepancyType.TEP_CROSS_SECTION_MISMATCH in inject:
        obj, f = rng.choice(text_mentions)
        key, true = mention_key(obj, "engineering_text", f), float(by_id[obj].tep[f])
        mode = rng.choice(("borderline", "large", "method"))
        if mode == "borderline":
            new = _near_tolerance(rng, true, tol.rel, tol.abs)
        elif mode == "large":
            new = _perturb(rng, true, 0.05, 0.6, 2)
        else:  # e.g. volume computed with a wrong height: several times off
            new = round(true * rng.uniform(3, 10), 2)
        values[key], decimals[key] = new, 2

    tot_tol = TOLERANCES[DiscrepancyType.TABLE_TOTAL_MISMATCH]
    if DiscrepancyType.TABLE_TOTAL_MISMATCH in inject and summary_fields:
        f = rng.choice(summary_fields)
        key = mention_key("all", "summary_total", f)
        true = float(values[key])
        mode = rng.choice(("borderline", "large", "neighbour"))
        others = [g for g in summary_fields if g != f
                  and not tot_tol.matches(float(values[mention_key("all", "summary_total", g)]), true)]
        if mode == "neighbour" and others:  # total copied from the next column
            new = values[mention_key("all", "summary_total", rng.choice(others))]
        elif mode == "borderline":
            new = _near_tolerance(rng, true, tot_tol.rel, tot_tol.abs)
        else:
            new = _perturb(rng, true, 0.02, 0.2, 2)
        values[key] = new

    param_kind = None
    if DiscrepancyType.PARAMETER_CONTRADICTION in inject:
        param_kind = rng.choice(("seismicity", "fire"))
        b = rng.choice(buildings)
        if param_kind == "seismicity":
            other = [p for p in SEISMIC_POINTS if abs(p - seismicity) == 1]
            values[mention_key(b.id, "object_section", "seismicity_points")] = rng.choice(other)
        else:
            other = [g for g in FIRE_GRADES if g != b.fire_resistance]
            values[mention_key(b.id, "fire_section", "fire_resistance")] = rng.choice(other)

    # ---------------------------------------------------------- ground truth records
    def ref(obj: str, place: str, fld: str) -> dict:
        key = mention_key(obj, place, fld)
        return {"object": obj, "section": Section.PZ.value, "field": fld, "place": place,
                "value": values[key], "mention": key}

    checks: list[dict] = []

    def numeric(dtype: DiscrepancyType, obj: str, fld: str, refs: list[dict], a: float, b: float) -> None:
        t = TOLERANCES[dtype]
        verdict = Verdict.MATCH if t.matches(a, b) else Verdict.MISMATCH
        rec = {"type": dtype.value, "object": obj, "field": fld, "refs": refs,
               "delta_abs": round(a - b, 3), "delta_rel": round((a - b) / b, 5) if b else None,
               "tolerance": {"rel": t.rel, "abs": t.abs}, "expected_verdict": verdict.value}
        (discrepancies if verdict == Verdict.MISMATCH else checks).append(rec)

    for f in summary_fields:
        rows = [ref(b.id, "summary_table", f) for b in buildings]
        total = ref("all", "summary_total", f)
        numeric(DiscrepancyType.TABLE_TOTAL_MISMATCH, "all", f, rows + [total],
                float(total["value"]), round(sum(float(r["value"]) for r in rows), 2))
    for obj, f in text_mentions:
        a, b = ref(obj, "object_table", f), ref(obj, "engineering_text", f)
        numeric(DiscrepancyType.TEP_CROSS_SECTION_MISMATCH, obj, f, [a, b], float(b["value"]), float(a["value"]))

    def categorical(obj: str, fld: str, refs: list[dict]) -> None:
        verdict = Verdict.MISMATCH if len({r["value"] for r in refs}) > 1 else Verdict.MATCH
        rec = {"type": DiscrepancyType.PARAMETER_CONTRADICTION.value, "object": obj, "field": fld, "refs": refs,
               "values": sorted({str(r["value"]) for r in refs}), "expected_verdict": verdict.value}
        (discrepancies if verdict == Verdict.MISMATCH else checks).append(rec)

    categorical("site", "seismicity_points", [ref("site", "site_general", "seismicity_points")]
                + [ref(b.id, "object_section", "seismicity_points") for b in buildings])
    for b in buildings:
        categorical(b.id, "fire_resistance", [ref(b.id, "object_section", "fire_resistance"),
                                              ref(b.id, "fire_section", "fire_resistance")])

    return PzPlan(buildings, seismicity, values, decimals, text_mentions, summary_fields, discrepancies, checks)
