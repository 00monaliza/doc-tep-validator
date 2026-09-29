"""Surface patterns of TEP fields in real documents (RU/KZ), shared by extraction and rules.

Header patterns are matched against repaired table headers; text patterns are
the label part of a phrase like "строительный объём здания ... 4963,84 м³".
Order matters: the first matching field wins.
"""

from __future__ import annotations

import re

FIELD_UNITS: dict[str, str] = {
    "construction_volume_m3": "m3",
    "building_area_m2": "m2",
    "useful_area_m2": "m2",
    "total_area_m2": "m2",
}

FIELD_HEADERS: dict[str, tuple[str, ...]] = {
    "floors": (r"этажн", r"қабат"),
    "building_area_m2": (r"застройк", r"құрылыс салу ауданы"),
    "useful_area_m2": (r"полезн", r"пайдалы"),
    "total_area_m2": (r"общ\w* площад", r"площад\w* общ", r"s\s*общ", r"жалпы аудан"),
    "construction_volume_m3": (r"строительн\w* объ[её]м", r"құрылыс көлем", r"объ[её]м"),
}

FIELD_TEXT: dict[str, tuple[str, ...]] = {
    "construction_volume_m3": (r"строительн\w*\s+объ[её]м\w*",
                               r"объ[её]м\w*\s+(?:здани\w*|корпус\w*|сооружени\w*)",
                               r"құрылыс\s+көлем\w*", r"ғимарат\w*\s+көлем\w*"),
    "building_area_m2": (r"площад\w*\s+застройк\w*", r"құрылыс\s+салу\s+аудан\w*"),
    "useful_area_m2": (r"полезн\w*\s+площад\w*", r"пайдалы\s+аудан\w*"),
    "total_area_m2": (r"общ\w*\s+площад\w*", r"площад\w*\s+общ\w*", r"жалпы\s+аудан\w*"),
}


def header_field(header: str) -> str | None:
    for fld, patterns in FIELD_HEADERS.items():
        if any(re.search(p, header, re.IGNORECASE) for p in patterns):
            return fld
    return None
