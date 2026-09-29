"""Profile v2 parts of the explanatory note (ПЗ), shared by the RU and KZ templates.

Language only enters through the lexicon (`PZ_V2`, names, label synonyms);
values and injected discrepancies come from `PzPlan` (values.py). Every
statement of a value is anchored under its `mention_key`, so ground truth can
point at the table cell or sentence.
"""

from __future__ import annotations

from types import ModuleType

from src.ner.common.taxonomy import Section
from src.synthesis.context import Ctx
from src.synthesis.document import Document, TableRows
from src.synthesis.formatting import fmt_num, fmt_styled, split_header_word
from src.synthesis.values import OBJECT_FIELDS, Building, mention_key

S = Section.PZ
_SENTINEL = "\x00{}\x00"


def names(lex: ModuleType, b: Building) -> tuple[str, str]:
    return lex.PRIMARY_SHORT[b.kind] if b.primary else lex.AUX_NAMES[b.kind]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def fill(template: str, anchored: dict[str, tuple[str, str]], **plain: str) -> tuple[str, dict]:
    """Format `template`; `anchored` maps placeholder -> (value text, anchor key).

    Returns the text and `Document.para` mentions with exact positions, so a
    value that also occurs elsewhere in the sentence ('II' ... 'II') is anchored
    at the right place.
    """
    marked = template.format(**plain, **{k: _SENTINEL.format(k) for k in anchored})
    text, mentions, pos = "", {}, 0
    for part in marked.split("\x00"):
        if part in anchored and pos % 2 == 1:
            value, key = anchored[part]
            mentions[key] = (value, len(text))
            text += value
        else:
            text += part
        pos += 1
    return text, mentions


def _num(value, style: str, decimals: int = 2) -> str:
    return fmt_styled(value, decimals, style)


def _header(ctx: Ctx, cells: list[str]) -> list[str]:
    """Some tables get words broken inside header cells, as in narrow Word columns."""
    if ctx.vrng.random() < 0.5:
        return cells
    return [split_header_word(c, ctx.vrng) if ctx.vrng.random() < 0.6 else c for c in cells]


def tep_table(ctx: Ctx, doc: Document, rows: list[tuple[str, str, str]], lex: ModuleType) -> None:
    """The ПЗ ТЭП table (`tbl_tep`) with label synonyms, unit spellings, column order and number style."""
    layout = ctx.vrng.choice(lex.TEP_HEADERS)
    roles = [role for role, _ in layout]
    style = ctx.style()
    t = TableRows()
    for fld, label, unit in rows:
        if ctx.get(S, fld) is None:
            continue
        synonyms = lex.TEP_LABELS.get(fld, (label,))
        cell = {"no": t.next_no, "value": ctx.fmt(S, fld, style),
                "unit": ctx.vrng.choice(lex.UNIT_VARIANTS.get(unit, (unit,))),
                "label": synonyms[0] if ctx.vrng.random() < 0.4 else ctx.vrng.choice(synonyms)}
        t.add([cell[r] for r in roles], {fld: roles.index("value")})
    widths = {"no": 0.09, "label": 0.55, "unit": 0.14, "value": 0.22}
    header = [text for _, text in layout]
    widths = [widths[r] / sum(widths[x] for x in roles) for r in roles]
    doc.add_rows(header, t, widths, "tbl_tep")


def site_seismic(ctx: Ctx, doc: Document, lex: ModuleType) -> None:
    p = ctx.plan
    key = mention_key("site", "site_general", "seismicity_points")
    text, mentions = fill(ctx.vrng.choice(lex.PZ_V2["site_seismic"]), {"s": (str(p.values[key]), key)})
    doc.para(text, mentions)


def summary_table(ctx: Ctx, doc: Document, lex: ModuleType) -> None:
    p, words = ctx.plan, lex.PZ_V2
    if not p.summary_fields:
        return
    fields = list(p.summary_fields)
    ctx.vrng.shuffle(fields)
    style = ctx.style()
    h = words["summary_header"]
    header = _header(ctx, [h["no"], h["name"]] + [h[f] for f in fields])
    t = TableRows()
    for b in p.buildings:
        cells = [t.next_no, names(lex, b)[0]]
        pos = {}
        for f in fields:
            key = mention_key(b.id, "summary_table", f)
            pos[key] = len(cells)
            cells.append(_num(p.values[key], style))
        t.add(cells, pos)
    cells, pos = ["", ctx.vrng.choice(words["summary_total"])], {}
    for f in fields:
        key = mention_key("all", "summary_total", f)
        pos[key] = len(cells)
        cells.append(_num(p.values[key], style))
    t.add(cells, pos, bold=True)
    doc.para(words["summary_intro"])
    rest = (1 - 0.08 - 0.34) / len(fields)
    doc.add_rows(header, t, [0.08, 0.34] + [rest] * len(fields), "tbl_objects")


def object_sections(ctx: Ctx, doc: Document, lex: ModuleType, first_no: int) -> int:
    """Sections per building, engineering and fire-safety sections; returns the next heading number."""
    p, words, rng = ctx.plan, lex.PZ_V2, ctx.vrng
    no = first_no
    doc.heading(f"{no}. {words['objects_heading']}")
    for k, b in enumerate(p.buildings, start=1):
        nom, gen = names(lex, b)
        doc.heading(f"{no}.{k} {nom}")
        if b.axes_m:
            a, bb = (fmt_num(x, 1) for x in b.axes_m)
            doc.para(words["object_axes"].format(name=nom, floors=b.tep["floors"], a=a, b=bb))
        else:
            doc.para(words["object_primary"].format(gen=gen, gen_cap=_cap(gen)))
        fields = [f for f in OBJECT_FIELDS if mention_key(b.id, "object_table", f) in p.values]
        rng.shuffle(fields)
        style = ctx.style()
        hdr, units = words["object_table_header"], words["object_table_units"]
        header = _header(ctx, [hdr["name"]] + [hdr[f] for f in fields])
        t = TableRows()
        t.add([units["name"]] + [units[f] for f in fields])
        cells, pos = [nom], {}
        for f in fields:
            key = mention_key(b.id, "object_table", f)
            pos[key] = len(cells)
            cells.append(_num(p.values[key], style))
        t.add(cells, pos)
        doc.para(words["object_table_caption"])
        doc.add_rows(header, t, [0.28] + [0.72 / len(fields)] * len(fields), f"tbl_obj_{b.id}")

        fire_key = mention_key(b.id, "object_section", "fire_resistance")
        text, mentions = fill(words["object_char"], {"fire": (str(p.values[fire_key]), fire_key)},
                              resp=b.responsibility)
        doc.para(text, mentions)
        s_key = mention_key(b.id, "object_section", "seismicity_points")
        text, mentions = fill(rng.choice(words["object_seismic"]), {"s": (str(p.values[s_key]), s_key)})
        doc.para(text, mentions)

    no += 1
    doc.heading(f"{no}. {words['eng_heading']}")
    doc.para(words["eng_intro"])
    by_id = {b.id: b for b in p.buildings}
    for obj, f in p.text_mentions:
        key = mention_key(obj, "engineering_text", f)
        gen = names(lex, by_id[obj])[1]
        value = _num(float(p.values[key]), ctx.style(), p.decimals[key])
        text, mentions = fill(rng.choice(words[f"eng_{f}"]), {"v": (value, key)}, gen=gen, gen_cap=_cap(gen))
        doc.para(text, mentions)

    no += 1
    doc.heading(f"{no}. {words['fire_heading']}")
    for b in p.buildings:
        key = mention_key(b.id, "fire_section", "fire_resistance")
        gen = names(lex, b)[1]
        text, mentions = fill(words["fire_line"], {"fire": (str(p.values[key]), key)}, gen=gen, gen_cap=_cap(gen))
        doc.para(text, mentions)
    return no + 1
