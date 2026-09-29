"""Түсіндірме жазба — ПЗ (KZ)."""

from src.ner.common.taxonomy import Section
from src.synthesis import pz_objects
from src.synthesis.context import Ctx
from src.synthesis.data import kz_lexicon as lex
from src.synthesis.document import Document, TableRows

S = Section.PZ


def build(ctx: Ctx) -> Document:
    m, v = ctx.meta, ctx.v
    doc = Document(S.value, "kz", f"{m.project_code}-ТЖ", "1-бөлім. Түсіндірме жазба")
    doc.title_block(f"«{m.object_name}», мекенжайы: {m.address}")

    doc.heading("1. Жалпы деректер")
    doc.para(ctx.pick(
        f"«{m.object_name}» объектісінің жобалау құжаттамасы {m.customer} бекіткен жобалауға арналған "
        f"тапсырма негізінде {m.designer} әзірледі.",
        f"Осы жоба тапсырыс беруші — {m.customer} берген жобалау тапсырмасына сәйкес {m.designer} "
        f"әзірлеген.",
    ))
    doc.para(f"Объектінің орналасқан жері: {m.address}. Бас жобалаушы: {m.designer}.")
    doc.para(f"Ғимараттың жауапкершілік деңгейі — II (қалыпты). Отқа төзімділік дәрежесі — II. "
             f"Функционалдық өрт қауіптілігі сыныбы — {v.fire_class}.")

    if ctx.v2:
        pz_objects.site_seismic(ctx, doc, lex)

    doc.heading("2. Техникалық-экономикалық көрсеткіштер")
    rows = [
        ("floors", "Қабат саны", "қабат"),
        ("building_area_m2", "Құрылыс салу ауданы", "м²"),
        ("total_area_m2", "Ғимараттың жалпы ауданы", "м²"),
        ("construction_volume_m3", "Құрылыс көлемі", "м³"),
        ("underground_volume_m3", "оның ішінде жерасты бөлігі", "м³"),
        ("estimated_cost_ktg", "Ағымдағы бағамен құрылыстың сметалық құны (ҚҚС-пен)", "мың теңге"),
        ("construction_duration_months", "Құрылыс ұзақтығы", "ай"),
    ]
    if ctx.v2:
        pz_objects.tep_table(ctx, doc, rows, lex)
    else:
        t = TableRows()
        for fld, label, unit in rows:
            if ctx.get(S, fld) is not None:
                t.add([t.next_no, label, unit, ctx.fmt(S, fld)], {fld: 3})
        doc.add_rows(["Р/с №", "Көрсеткіштің атауы", "Өлш. бірл.", "Мәні"], t,
                     [0.09, 0.55, 0.14, 0.22], "tbl_tep")

    style = ctx.style()
    area = ctx.fmt(S, "total_area_m2", style)
    if ctx.get(S, "construction_volume_m3") is not None:
        vol = ctx.fmt(S, "construction_volume_m3", style)
        doc.para(ctx.pick(
            f"Ғимараттың жалпы ауданы {area} м², құрылыс көлемі — {vol} м³ құрайды.",
            f"Жобада құрылыс көлемі {vol} м³ болғанда ғимараттың жалпы ауданы {area} м² деп қабылданған.",
        ), {"total_area_m2": area, "construction_volume_m3": vol})
    else:
        doc.para(f"Ғимараттың жалпы ауданы {area} м² құрайды.", {"total_area_m2": area})

    no = 3
    if ctx.v2:
        pz_objects.summary_table(ctx, doc, lex)
        no = pz_objects.object_sections(ctx, doc, lex, no)

    doc.heading(f"{no}. Сметалық құн туралы мәліметтер")
    if ctx.get(S, "estimated_cost_ktg") is not None:
        cost = ctx.fmt(S, "estimated_cost_ktg")
        doc.para(f"Құрылыстың сметалық құны {m.year} жылғы ағымдағы бағамен ресурстық әдіспен анықталды және "
                 f"12 % ҚҚС-ты қоса алғанда {cost} мың теңгені құрайды.", {"estimated_cost_ktg": cost})
    else:
        doc.para(f"Сметалық құжаттама {m.year} жылғы ағымдағы бағамен ресурстық әдіспен жергілікті, "
                 f"объектілік сметалар және жиынтық сметалық есеп құрамында әзірленді.")
    doc.para(f"Жобаның бас инженері: {m.chief_engineer}.")
    return doc
