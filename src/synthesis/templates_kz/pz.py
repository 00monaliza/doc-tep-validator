"""Түсіндірме жазба — ПЗ (KZ)."""

from src.ner.common.taxonomy import Section
from src.synthesis.context import Ctx
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

    doc.heading("2. Техникалық-экономикалық көрсеткіштер")
    t = TableRows()
    rows = [
        ("floors", "Қабат саны", "қабат"),
        ("building_area_m2", "Құрылыс салу ауданы", "м²"),
        ("total_area_m2", "Ғимараттың жалпы ауданы", "м²"),
        ("construction_volume_m3", "Құрылыс көлемі", "м³"),
        ("underground_volume_m3", "оның ішінде жерасты бөлігі", "м³"),
        ("estimated_cost_ktg", "Ағымдағы бағамен құрылыстың сметалық құны (ҚҚС-пен)", "мың теңге"),
        ("construction_duration_months", "Құрылыс ұзақтығы", "ай"),
    ]
    for fld, label, unit in rows:
        if ctx.get(S, fld) is not None:
            t.add([t.next_no, label, unit, ctx.fmt(S, fld)], {fld: 3})
    doc.add_rows(["Р/с №", "Көрсеткіштің атауы", "Өлш. бірл.", "Мәні"], t,
                 [0.09, 0.55, 0.14, 0.22], "tbl_tep")

    area = ctx.fmt(S, "total_area_m2")
    if ctx.get(S, "construction_volume_m3") is not None:
        vol = ctx.fmt(S, "construction_volume_m3")
        doc.para(ctx.pick(
            f"Ғимараттың жалпы ауданы {area} м², құрылыс көлемі — {vol} м³ құрайды.",
            f"Жобада құрылыс көлемі {vol} м³ болғанда ғимараттың жалпы ауданы {area} м² деп қабылданған.",
        ), {"total_area_m2": area, "construction_volume_m3": vol})
    else:
        doc.para(f"Ғимараттың жалпы ауданы {area} м² құрайды.", {"total_area_m2": area})

    doc.heading("3. Сметалық құн туралы мәліметтер")
    if ctx.get(S, "estimated_cost_ktg") is not None:
        cost = ctx.fmt(S, "estimated_cost_ktg")
        doc.para(f"Құрылыстың сметалық құны {m.year} жылғы ағымдағы бағамен ресурстық әдіспен анықталды және "
                 f"12 % ҚҚС-ты қоса алғанда {cost} мың теңгені құрайды.", {"estimated_cost_ktg": cost})
    else:
        doc.para(f"Сметалық құжаттама {m.year} жылғы ағымдағы бағамен ресурстық әдіспен жергілікті, "
                 f"объектілік сметалар және жиынтық сметалық есеп құрамында әзірленді.")
    doc.para(f"Жобаның бас инженері: {m.chief_engineer}.")
    return doc
