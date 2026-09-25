"""Kazakh lexical patterns for the rule-based TEP extractor (regex, case-insensitive).

Stems cover Kazakh case endings (ауданы / ауданын / ауданның ...).
"""

TEP_ROW = [
    ("underground_volume_m3", r"жерасты"),
    ("floors", r"қабат саны|қабаттылығы"),
    ("building_area_m2", r"құрылыс салу аудан"),
    ("total_area_m2", r"жалпы аудан"),
    ("construction_volume_m3", r"құрылыс көлем"),
    ("estimated_cost_ktg", r"сметалық құн"),
    ("construction_duration_months", r"құрылыс ұзақтығ"),
]
MATERIAL_ROW = [
    ("rebar_a500c_t", r"арматура"),
    ("steel_structures_t", r"болат конструкц|металл конструкц"),
    ("brick_masonry_m3", r"кірпіш"),
    ("concrete_b25_foundation_m3", r"[BВ]\s?25"),
    ("concrete_b30_frame_m3", r"[BВ]\s?30"),
]
HEADER = {
    "label": r"атауы|көрсеткіш",
    "value": r"мәні",
    "qty": r"саны|мөлшері",
    "price": r"бағасы",
    "area": r"аудан",
    "estimate_no": r"смета нөмірі",
    "unit": r"өлш",
}
TABLE_CONTEXT = {
    "explication": r"экспликация",
    "materials": r"көлемдерінің ведомос|материалдар шығын",
    "object": r"объектілік смета",
    "summary": r"жиынтық сметалық",
    "local": r"жергілікті смета",
}
TOTAL_ROW = {
    "explication_total": r"жалпы аудан",
    "floor_subtotal": r"қабат бойынша",
    "object_total": r"объектілік смета бойынша",
    "summary_total": r"жиынтық сметалық есеп бойынша",
    "local_total": r"жергілікті смета бойынша",
}
PARAGRAPH = {
    "total_area_m2": r"жалпы аудан\w*",
    "construction_volume_m3": r"құрылыс көлем\w*",
    "estimated_cost_ktg": r"сметалық құн\w*",
    "concrete_total_m3": r"бетонның жалпы шығын\w*",
}
FLOORS_IN_TEXT = r"(\d+) қабатты"
COST_UNIT_THOUSANDS = r"мың теңге"
