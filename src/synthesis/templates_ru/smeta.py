"""Сметная документация: локальная смета, объектная смета, сводный сметный расчёт (RU)."""

from src.ner.common.taxonomy import MATERIALS, Section
from src.synthesis.context import NORM_CODES, Ctx
from src.synthesis.data import ru_lexicon as lex
from src.synthesis.document import Document, TableRows
from src.synthesis.values import OBJECT_ESTIMATE_NO, OBJECT_ESTIMATE_ROWS

S = Section.SMETA


def build(ctx: Ctx) -> Document:
    m = ctx.meta
    doc = Document(S.value, "ru", f"{m.project_code}-СД", "Раздел 9. Сметная документация")
    doc.title_block(f"«{m.object_name}»")

    # --- Локальная смета
    doc.heading("Локальная смета № 02-01-01")
    doc.para(f"на железобетонные и каменные конструкции. Объект: «{m.object_name}». "
             f"Основание: чертежи марок КЖ, КР. Составлена ресурсным методом в текущих ценах {m.year} г.")
    t = TableRows()
    for mat in MATERIALS:
        _, unit = lex.MATERIALS[mat]
        t.add([t.next_no, NORM_CODES[mat], lex.ESTIMATE_WORKS[mat], unit,
               ctx.fmt(S, f"local_qty.{mat}"), ctx.fmt(S, f"local_unit_price_tg.{mat}"),
               ctx.fmt(S, f"local_cost_tg.{mat}")],
              {f"local_qty.{mat}": 4, f"local_unit_price_tg.{mat}": 5, f"local_cost_tg.{mat}": 6})
    t.add(["", "", "Итого прямые затраты", "", "", "", ctx.fmt(S, "local.direct_tg")],
          {"local.direct_tg": 6}, bold=True)
    t.add(["", "", f"Накладные расходы, {ctx.fmt(S, 'local.overhead_pct')} %", "", "", "",
           ctx.fmt(S, "local.overhead_tg")], {"local.overhead_tg": 6, "local.overhead_pct": 2})
    t.add(["", "", f"Сметная прибыль, {ctx.fmt(S, 'local.profit_pct')} %", "", "", "",
           ctx.fmt(S, "local.profit_tg")], {"local.profit_tg": 6, "local.profit_pct": 2})
    t.add(["", "", "Всего по локальной смете", "", "", "", ctx.fmt(S, "local.total_tg")],
          {"local.total_tg": 6}, bold=True)
    doc.add_rows(["№ п/п", "Шифр норматива", "Наименование работ и затрат", "Ед. изм.", "Кол-во",
                  "Цена за ед., тенге", "Стоимость, тенге"], t,
                 [0.06, 0.14, 0.32, 0.07, 0.11, 0.14, 0.16], "tbl_local")

    # --- Объектная смета
    doc.heading(f"Объектная смета № {OBJECT_ESTIMATE_NO}")
    doc.para(f"на строительство объекта «{m.object_name}». Сметная стоимость в тыс. тенге.")
    t = TableRows()
    for ls_no, (kind, _) in OBJECT_ESTIMATE_ROWS.items():
        fld = f"os.ls_{ls_no}_ktg"
        t.add([t.next_no, f"ЛС {ls_no}", lex.OBJECT_ESTIMATE_ROWS[kind], ctx.fmt(S, fld)], {fld: 3})
    t.add(["", "", "Итого по объектной смете", ctx.fmt(S, "os.total_ktg")], {"os.total_ktg": 3}, bold=True)
    doc.add_rows(["№ п/п", "Номер сметы", "Наименование работ и затрат", "Сметная стоимость, тыс. тенге"], t,
                 [0.08, 0.17, 0.50, 0.25], "tbl_object")

    # --- Сводный сметный расчёт
    doc.heading("Сводный сметный расчёт стоимости строительства")
    doc.para(f"Объект: «{m.object_name}». Заказчик: {m.customer}. Составлен в текущих ценах {m.year} г.")
    ch2 = f"ssr.ch2.os_{OBJECT_ESTIMATE_NO}_ktg"
    t = TableRows()
    t.add([t.next_no, "", "Глава 1. Подготовка территории строительства", ctx.fmt(S, "ssr.ch1_ktg")],
          {"ssr.ch1_ktg": 3})
    t.add(["", "", "Глава 2. Основные объекты строительства", ""], bold=True)
    t.add([t.next_no, f"ОС {OBJECT_ESTIMATE_NO}", m.object_name, ctx.fmt(S, ch2)], {ch2: 3})
    for fld, label in (("ssr.ch7_ktg", "Глава 7. Благоустройство и озеленение территории"),
                       ("ssr.ch8_ktg", "Глава 8. Временные здания и сооружения"),
                       ("ssr.ch9_ktg", "Глава 9. Прочие работы и затраты"),
                       ("ssr.ch12_ktg", "Глава 12. Проектные и изыскательские работы")):
        t.add([t.next_no, "", label, ctx.fmt(S, fld)], {fld: 3})
    t.add(["", "", "Итого по главам 1–12", ctx.fmt(S, "ssr.subtotal_ktg")], {"ssr.subtotal_ktg": 3}, bold=True)
    t.add(["", "", "Резерв средств на непредвиденные работы и затраты, 2 %", ctx.fmt(S, "ssr.reserve_ktg")],
          {"ssr.reserve_ktg": 3})
    t.add(["", "", "Итого с учётом непредвиденных затрат", ctx.fmt(S, "ssr.with_reserve_ktg")],
          {"ssr.with_reserve_ktg": 3}, bold=True)
    t.add(["", "", "НДС 12 %", ctx.fmt(S, "ssr.vat_ktg")], {"ssr.vat_ktg": 3})
    t.add(["", "", "Всего по сводному сметному расчёту", ctx.fmt(S, "ssr.total_ktg")],
          {"ssr.total_ktg": 3}, bold=True)
    doc.add_rows(["№ п/п", "Номер сметы", "Наименование глав, объектов, работ и затрат",
                  "Сметная стоимость, тыс. тенге"], t, [0.08, 0.14, 0.53, 0.25], "tbl_summary")
    return doc
