"""Сметалық құжаттама: жергілікті смета, объектілік смета, жиынтық сметалық есеп (KZ)."""

from src.ner.common.taxonomy import MATERIALS, Section
from src.synthesis.context import NORM_CODES, Ctx
from src.synthesis.data import kz_lexicon as lex
from src.synthesis.document import Document, TableRows
from src.synthesis.values import OBJECT_ESTIMATE_NO, OBJECT_ESTIMATE_ROWS

S = Section.SMETA


def build(ctx: Ctx) -> Document:
    m = ctx.meta
    doc = Document(S.value, "kz", f"{m.project_code}-СҚ", "9-бөлім. Сметалық құжаттама")
    doc.title_block(f"«{m.object_name}»")

    # --- Жергілікті смета
    doc.heading("№ 02-01-01 жергілікті смета")
    doc.para(f"Темірбетон және тас конструкцияларға. Объект: «{m.object_name}». "
             f"Негіздеме: КЖ, КШ маркалы сызбалар. {m.year} жылғы ағымдағы бағамен ресурстық әдіспен жасалды.")
    t = TableRows()
    for mat in MATERIALS:
        _, unit = lex.MATERIALS[mat]
        t.add([t.next_no, NORM_CODES[mat], lex.ESTIMATE_WORKS[mat], unit,
               ctx.fmt(S, f"local_qty.{mat}"), ctx.fmt(S, f"local_unit_price_tg.{mat}"),
               ctx.fmt(S, f"local_cost_tg.{mat}")],
              {f"local_qty.{mat}": 4, f"local_unit_price_tg.{mat}": 5, f"local_cost_tg.{mat}": 6})
    t.add(["", "", "Тікелей шығындар, барлығы", "", "", "", ctx.fmt(S, "local.direct_tg")],
          {"local.direct_tg": 6}, bold=True)
    t.add(["", "", f"Үстеме шығыстар, {ctx.fmt(S, 'local.overhead_pct')} %", "", "", "",
           ctx.fmt(S, "local.overhead_tg")], {"local.overhead_tg": 6, "local.overhead_pct": 2})
    t.add(["", "", f"Сметалық пайда, {ctx.fmt(S, 'local.profit_pct')} %", "", "", "",
           ctx.fmt(S, "local.profit_tg")], {"local.profit_tg": 6, "local.profit_pct": 2})
    t.add(["", "", "Жергілікті смета бойынша барлығы", "", "", "", ctx.fmt(S, "local.total_tg")],
          {"local.total_tg": 6}, bold=True)
    doc.add_rows(["Р/с №", "Норматив шифры", "Жұмыстар мен шығындардың атауы", "Өлш. бірл.", "Саны",
                  "Бірлік бағасы, теңге", "Құны, теңге"], t,
                 [0.06, 0.14, 0.32, 0.07, 0.11, 0.14, 0.16], "tbl_local")

    # --- Объектілік смета
    doc.heading(f"№ {OBJECT_ESTIMATE_NO} объектілік смета")
    doc.para(f"«{m.object_name}» объектісінің құрылысына. Сметалық құны мың теңгемен көрсетілген.")
    t = TableRows()
    for ls_no, (kind, _) in OBJECT_ESTIMATE_ROWS.items():
        fld = f"os.ls_{ls_no}_ktg"
        t.add([t.next_no, f"ЖС {ls_no}", lex.OBJECT_ESTIMATE_ROWS[kind], ctx.fmt(S, fld)], {fld: 3})
    t.add(["", "", "Объектілік смета бойынша жиыны", ctx.fmt(S, "os.total_ktg")], {"os.total_ktg": 3}, bold=True)
    doc.add_rows(["Р/с №", "Смета нөмірі", "Жұмыстар мен шығындардың атауы", "Сметалық құны, мың теңге"], t,
                 [0.08, 0.17, 0.50, 0.25], "tbl_object")

    # --- Жиынтық сметалық есеп
    doc.heading("Құрылыстың сметалық құнының жиынтық сметалық есебі")
    doc.para(f"Объект: «{m.object_name}». Тапсырыс беруші: {m.customer}. {m.year} жылғы ағымдағы бағамен жасалды.")
    ch2 = f"ssr.ch2.os_{OBJECT_ESTIMATE_NO}_ktg"
    t = TableRows()
    t.add([t.next_no, "", "1-тарау. Құрылыс аумағын дайындау", ctx.fmt(S, "ssr.ch1_ktg")], {"ssr.ch1_ktg": 3})
    t.add(["", "", "2-тарау. Құрылыстың негізгі объектілері", ""], bold=True)
    t.add([t.next_no, f"ОС {OBJECT_ESTIMATE_NO}", m.object_name, ctx.fmt(S, ch2)], {ch2: 3})
    for fld, label in (("ssr.ch7_ktg", "7-тарау. Аумақты абаттандыру және көгалдандыру"),
                       ("ssr.ch8_ktg", "8-тарау. Уақытша ғимараттар мен құрылыстар"),
                       ("ssr.ch9_ktg", "9-тарау. Басқа жұмыстар мен шығындар"),
                       ("ssr.ch12_ktg", "12-тарау. Жобалау және іздестіру жұмыстары")):
        t.add([t.next_no, "", label, ctx.fmt(S, fld)], {fld: 3})
    t.add(["", "", "1–12-тараулар бойынша жиыны", ctx.fmt(S, "ssr.subtotal_ktg")],
          {"ssr.subtotal_ktg": 3}, bold=True)
    t.add(["", "", "Күтпеген жұмыстар мен шығындарға арналған қаражат резерві, 2 %",
           ctx.fmt(S, "ssr.reserve_ktg")], {"ssr.reserve_ktg": 3})
    t.add(["", "", "Күтпеген шығындарды қоса алғандағы жиыны", ctx.fmt(S, "ssr.with_reserve_ktg")],
          {"ssr.with_reserve_ktg": 3}, bold=True)
    t.add(["", "", "ҚҚС 12 %", ctx.fmt(S, "ssr.vat_ktg")], {"ssr.vat_ktg": 3})
    t.add(["", "", "Жиынтық сметалық есеп бойынша барлығы", ctx.fmt(S, "ssr.total_ktg")],
          {"ssr.total_ktg": 3}, bold=True)
    doc.add_rows(["Р/с №", "Смета нөмірі", "Тараулардың, объектілердің, жұмыстар мен шығындардың атауы",
                  "Сметалық құны, мың теңге"], t, [0.08, 0.14, 0.53, 0.25], "tbl_summary")
    return doc
