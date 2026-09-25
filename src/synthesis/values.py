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
