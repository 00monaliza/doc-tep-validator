"""Russian lexical patterns for the rule-based TEP extractor (regex, case-insensitive).

Patterns use word stems, not the synthetic templates' exact wording, so they
also cover typical real-document variants ("объем"/"объём", "кол-во"...).
"""

# Row label -> TEP field (first match wins; more specific first).
TEP_ROW = [
    ("underground_volume_m3", r"подземн"),
    ("floors", r"этажност|количество этажей|число этажей"),
    ("building_area_m2", r"площадь застройки"),
    ("total_area_m2", r"общая площадь"),
    ("construction_volume_m3", r"строительн\w* объ[её]м"),
    ("estimated_cost_ktg", r"сметн\w* стоимост"),
    ("construction_duration_months", r"продолжительност\w* строительств"),
]
MATERIAL_ROW = [
    ("rebar_a500c_t", r"арматур|армирован"),
    ("steel_structures_t", r"стальн\w* конструкц|металлоконструкц|металлическ\w* конструкц"),
    ("brick_masonry_m3", r"кирпич"),
    ("concrete_b25_foundation_m3", r"[BВ]\s?25"),
    ("concrete_b30_frame_m3", r"[BВ]\s?30"),
]
HEADER = {
    "label": r"наименован|показател",
    "value": r"значени|величин",
    "qty": r"кол-во|количеств",
    "price": r"цена",
    "area": r"площадь",
    "estimate_no": r"номер смет|№ смет",
    "unit": r"ед\.? ?изм",
}
TABLE_CONTEXT = {
    "explication": r"экспликац",
    "materials": r"ведомост\w* объ[её]м|расход\w* материал",
    "object": r"объектн\w* смет",
    "summary": r"сводн\w* сметн",
    "local": r"локальн\w* смет",
}
TOTAL_ROW = {
    "explication_total": r"итого общая площадь|общая площадь|итого по зданию",
    "floor_subtotal": r"итого по \d+ этаж|итого по этажу",
    "object_total": r"итого по объектн",
    "summary_total": r"всего по сводн",
    "local_total": r"всего по локальн",
}
PARAGRAPH = {
    "total_area_m2": r"общ\w* площад\w* здани\w*",
    "construction_volume_m3": r"строительн\w* объ[её]м\w*",
    "estimated_cost_ktg": r"сметн\w* стоимост\w* строительств\w*",
    "concrete_total_m3": r"расход\w* монолитн\w* бетон\w*",
}
FLOORS_IN_TEXT = r"(\d+)-этажн"
COST_UNIT_THOUSANDS = r"тыс\.? ?тенге|тыс\.? ?тг"
