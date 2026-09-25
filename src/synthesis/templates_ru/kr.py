"""КР — конструктивные решения, текстовая часть с ведомостью объёмов (RU)."""

from src.ner.common.taxonomy import MATERIALS, Section
from src.synthesis.context import Ctx
from src.synthesis.data import ru_lexicon as lex
from src.synthesis.document import Document, TableRows

S = Section.KR


def build(ctx: Ctx) -> Document:
    m, v = ctx.meta, ctx.v
    doc = Document(S.value, "ru", f"{m.project_code}-КР", "Раздел 4. Конструктивные решения. Текстовая часть")
    doc.title_block(f"«{m.object_name}»")

    doc.heading("1. Конструктивная схема")
    doc.para(ctx.pick(
        "Конструктивная схема здания — каркасная, с монолитными железобетонными колоннами и плитами "
        "перекрытий. Пространственная жёсткость обеспечивается совместной работой колонн, диафрагм и дисков "
        "перекрытий.",
        "Здание запроектировано в монолитном железобетонном каркасе с жёсткими узлами сопряжения колонн "
        "и плит перекрытий.",
    ))
    doc.para(f"Фундаменты — монолитная железобетонная плита толщиной {v.foundation_thickness_mm} мм "
             f"из бетона класса B25, W6, F150. Наружные стены — кладка из керамического кирпича.")

    doc.heading("2. Ведомость объёмов основных конструктивных материалов")
    t = TableRows()
    for mat in MATERIALS:
        if ctx.get(S, mat) is not None:
            label, unit = lex.MATERIALS[mat]
            t.add([t.next_no, label, unit, ctx.fmt(S, mat)], {mat: 3})
    doc.add_rows(["№ п/п", "Наименование конструкций, материалов", "Ед. изм.", "Количество"], t,
                 [0.09, 0.59, 0.12, 0.20], "tbl_materials")

    total = ctx.fmt(S, "concrete_total_m3")
    doc.para(f"Общий расход монолитного бетона составляет {total} м³.", {"concrete_total_m3": total})
    return doc
