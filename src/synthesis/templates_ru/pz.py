"""ПЗ — пояснительная записка (RU)."""

from src.ner.common.taxonomy import Section
from src.synthesis import pz_objects
from src.synthesis.context import Ctx
from src.synthesis.data import ru_lexicon as lex
from src.synthesis.document import Document, TableRows

S = Section.PZ


def build(ctx: Ctx) -> Document:
    m, v = ctx.meta, ctx.v
    doc = Document(S.value, "ru", f"{m.project_code}-ПЗ", "Раздел 1. Пояснительная записка")
    doc.title_block(f"«{m.object_name}» по адресу: {m.address}")

    doc.heading("1. Общие данные")
    doc.para(ctx.pick(
        f"Проектная документация по объекту «{m.object_name}» разработана {m.designer} на основании "
        f"задания на проектирование, утверждённого {m.customer}.",
        f"Настоящий проект разработан {m.designer} в соответствии с заданием на проектирование, "
        f"выданным заказчиком — {m.customer}.",
    ))
    doc.para(f"Место размещения объекта: {m.address}. Заказчик: {m.customer}. "
             f"Генеральный проектировщик: {m.designer}.")
    doc.para(f"Уровень ответственности здания — II (нормальный). Степень огнестойкости — II. "
             f"Класс функциональной пожарной опасности — {v.fire_class}.")

    if ctx.v2:
        pz_objects.site_seismic(ctx, doc, lex)

    doc.heading("2. Технико-экономические показатели")
    rows = [
        ("floors", "Этажность", "этаж"),
        ("building_area_m2", "Площадь застройки", "м²"),
        ("total_area_m2", "Общая площадь здания", "м²"),
        ("construction_volume_m3", "Строительный объём", "м³"),
        ("underground_volume_m3", "в том числе подземной части", "м³"),
        ("estimated_cost_ktg", "Сметная стоимость строительства в текущих ценах (с НДС)", "тыс. тенге"),
        ("construction_duration_months", "Продолжительность строительства", "мес."),
    ]
    if ctx.v2:
        pz_objects.tep_table(ctx, doc, rows, lex)
    else:
        t = TableRows()
        for fld, label, unit in rows:
            if ctx.get(S, fld) is not None:
                t.add([t.next_no, label, unit, ctx.fmt(S, fld)], {fld: 3})
        doc.add_rows(["№ п/п", "Наименование показателя", "Ед. изм.", "Значение"], t,
                     [0.09, 0.55, 0.14, 0.22], "tbl_tep")

    style = ctx.style()
    area = ctx.fmt(S, "total_area_m2", style)
    if ctx.get(S, "construction_volume_m3") is not None:
        vol = ctx.fmt(S, "construction_volume_m3", style)
        doc.para(ctx.pick(
            f"Общая площадь здания составляет {area} м², строительный объём — {vol} м³.",
            f"Проектом принята общая площадь здания {area} м² при строительном объёме {vol} м³.",
        ), {"total_area_m2": area, "construction_volume_m3": vol})
    else:
        doc.para(f"Общая площадь здания составляет {area} м².", {"total_area_m2": area})

    no = 3
    if ctx.v2:
        pz_objects.summary_table(ctx, doc, lex)
        no = pz_objects.object_sections(ctx, doc, lex, no)

    doc.heading(f"{no}. Сведения о сметной стоимости")
    if ctx.get(S, "estimated_cost_ktg") is not None:
        cost = ctx.fmt(S, "estimated_cost_ktg")
        doc.para(f"Сметная стоимость строительства определена ресурсным методом в текущих ценах "
                 f"{m.year} г. и составляет {cost} тыс. тенге, в том числе НДС 12 %.",
                 {"estimated_cost_ktg": cost})
    else:
        doc.para(f"Сметная документация разработана ресурсным методом в текущих ценах {m.year} г. "
                 f"в составе локальных, объектных смет и сводного сметного расчёта.")
    doc.para(f"Главный инженер проекта: {m.chief_engineer}.")
    return doc
