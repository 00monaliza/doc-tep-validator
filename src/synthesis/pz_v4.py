"""Profile v4 parts of the ПЗ (RU/KZ): relief, elevation 0.000, heights, blind area, roof, table labels."""

from __future__ import annotations

from types import ModuleType

from src.synthesis.context import Ctx
from src.synthesis.document import Document
from src.synthesis.formatting import fmt_num
from src.synthesis.pz_objects import fill, names
from src.synthesis.values import Building, mention_key


def _width(ctx: Ctx, width_mm: int, words: dict) -> str:
    if ctx.v4rng.random() < 0.5:
        return f"{width_mm} {words['mm']}"
    return f"{fmt_num(width_mm / 1000, 1)} {words['m']}"


def _blind(ctx: Ctx, value: str, words: dict) -> tuple[str, str]:
    material, width = value.split(", ")
    return words["materials"][material], _width(ctx, int(width.split()[0]), words)


def site_relief(ctx: Ctx, doc: Document, lex: ModuleType) -> None:
    v, words = ctx.v4.values, lex.PZ_V4
    lo_key, hi_key = mention_key("site", "relief", "relief_min_m"), mention_key("site", "relief", "relief_max_m")
    text, mentions = fill(ctx.v4rng.choice(words["relief"]),
                          {"lo": (fmt_num(v[lo_key], 2), lo_key), "hi": (fmt_num(v[hi_key], 2), hi_key)})
    doc.para(text, mentions)


def table_label(ctx: Ctx, lex: ModuleType, b: Building) -> str:
    """Object name in the building's ТЭП table: its own, or another building's (COPY_PASTE_LABEL)."""
    other = ctx.v4.labels[b.id]
    by_id = {x.id: x for x in ctx.plan.buildings}
    name = names(lex, by_id[other] if other else b)[0]
    ctx.v4.values[mention_key(b.id, "object_table", "object_label")] = name
    return name


def building_extras(ctx: Ctx, doc: Document, lex: ModuleType, b: Building) -> None:
    v, words = ctx.v4.values, lex.PZ_V4
    z_key = mention_key(b.id, "object_section", "absolute_elevation_m")
    text, mentions = fill(ctx.v4rng.choice(words["elevation"]), {"z": (fmt_num(v[z_key], 2), z_key)})
    doc.para(text, mentions)
    fh_key = mention_key(b.id, "object_section", "floor_height_m")
    ch_key = mention_key(b.id, "object_section", "clear_height_m")
    text, mentions = fill(words["heights"], {"fh": (fmt_num(v[fh_key], 2), fh_key),
                                             "ch": (fmt_num(v[ch_key], 2), ch_key)})
    doc.para(text, mentions)
    ba_key, roof_key = mention_key(b.id, "object_section", "blind_area"), mention_key(b.id, "object_section", "roof")
    material, width = _blind(ctx, str(v[ba_key]), words)
    text, mentions = fill(words["blind_area"], {"material": (material, ba_key)}, width=width)
    doc.para(text, mentions)
    text, mentions = fill(words["roof"], {"roof": (words["roofs"][v[roof_key]], roof_key)})
    doc.para(text, mentions)


def general_section(ctx: Ctx, doc: Document, lex: ModuleType, no: int) -> int:
    v, words = ctx.v4.values, lex.PZ_V4
    doc.heading(f"{no}. {words['landscaping_heading']}")
    ba_key, roof_key = mention_key("all", "landscaping", "blind_area"), mention_key("all", "landscaping", "roof")
    material, width = _blind(ctx, str(v[ba_key]), words)
    text, mentions = fill(words["landscaping_blind_area"], {"material": (material, ba_key)}, width=width)
    doc.para(text, mentions)
    text, mentions = fill(words["landscaping_roof"], {"roof": (words["roofs"][v[roof_key]], roof_key)})
    doc.para(text, mentions)
    return no + 1
