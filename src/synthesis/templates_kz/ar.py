"""Сәулет шешімдері — мәтіндік бөлігі және үй-жайлар экспликациясы (KZ)."""

from src.ner.common.taxonomy import Section
from src.synthesis.context import Ctx
from src.synthesis.data import kz_lexicon as lex
from src.synthesis.document import Document, TableRows
from src.synthesis.formatting import fmt_num

S = Section.AR


def build(ctx: Ctx) -> Document:
    m, v = ctx.meta, ctx.v
    doc = Document(S.value, "kz", f"{m.project_code}-СШ", "3-бөлім. Сәулет шешімдері. Мәтіндік бөлігі")
    doc.title_block(f"«{m.object_name}»")

    doc.heading("1. Жалпы нұсқаулар")
    doc.para(f"«{m.object_name}» объектісінің сәулет шешімдері жобалау тапсырмасына және Қазақстан "
             f"Республикасының қолданыстағы құрылыс нормаларына сәйкес әзірленді.")

    doc.heading("2. Көлемдік-жоспарлау шешімдері")
    a, b = (fmt_num(x, 1) for x in v.axes_m)
    basement = ", техникалық жертөлесі бар" if v.has_basement else ""
    doc.para(f"Ғимарат {v.floors} қабатты{basement}, жоспарда тікбұрышты, осьтердегі өлшемдері {a} × {b} м. "
             f"Қабат биіктігі — {fmt_num(v.floor_height_m, 1)} м.")
    doc.para(ctx.pick(
        "Жиһаз бен технологиялық жабдықтарды орналастыру үй-жайлардың функционалдық мақсатына сәйкес "
        "орындалды.",
        "Жоспарлау шешімдері үй-жайлардың нормативтік байланысын және эвакуация жолдарын қамтамасыз етеді; "
        "жиһаз орналастыру сызбасы қоса беріледі.",
    ))
    t = TableRows()
    t.add([t.next_no, "Қабат саны", "қабат", ctx.fmt(S, "floors")], {"floors": 3})
    t.add([t.next_no, "Құрылыс салу ауданы", "м²", ctx.fmt(S, "building_area_m2")], {"building_area_m2": 3})
    t.add([t.next_no, "Құрылыс көлемі", "м³", ctx.fmt(S, "construction_volume_m3")],
          {"construction_volume_m3": 3})
    doc.add_rows(["Р/с №", "Көрсеткіш", "Өлш. бірл.", "Мәні"], t, [0.09, 0.55, 0.14, 0.22], "tbl_ar_tep")

    doc.heading("3. Үй-жайлар экспликациясы")
    t = TableRows()
    for floor in range(1, v.floors + 1):
        t.add(["", f"{floor}-қабат", "", ""], bold=True)
        rooms = [r for r in v.rooms if r.floor == floor]
        for r in rooms:
            t.add([r.number, lex.ROOMS[r.kind], fmt_num(r.area_m2), r.category], {f"room.{r.number}.area_m2": 2})
        t.add(["", f"{floor}-қабат бойынша барлығы", fmt_num(sum(r.area_m2 for r in rooms)), ""], bold=True)
    t.add(["", "Ғимараттың жалпы ауданы, барлығы", ctx.fmt(S, "explication_total_area_m2"), ""],
          {"explication_total_area_m2": 2}, bold=True)
    doc.add_rows(["Үй-жай №", "Атауы", "Ауданы, м²", "Санаты"], t, [0.12, 0.56, 0.18, 0.14],
                 "tbl_explication")

    doc.heading("4. Үй-жайларды әрлеу")
    doc.para("Ішкі әрлеу үй-жайларды әрлеу ведомосына сәйкес орындалады. Санитариялық тораптар мен ылғалды "
             "режимдегі үй-жайлардың едені — керамикалық плитка.")
    return doc
