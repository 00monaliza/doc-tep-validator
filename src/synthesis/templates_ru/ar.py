"""АР — архитектурные решения, текстовая часть с экспликацией помещений (RU)."""

from src.ner.common.taxonomy import Section
from src.synthesis.context import Ctx
from src.synthesis.data import ru_lexicon as lex
from src.synthesis.document import Document, TableRows
from src.synthesis.formatting import fmt_num

S = Section.AR


def build(ctx: Ctx) -> Document:
    m, v = ctx.meta, ctx.v
    doc = Document(S.value, "ru", f"{m.project_code}-АР", "Раздел 3. Архитектурные решения. Текстовая часть")
    doc.title_block(f"«{m.object_name}»")

    doc.heading("1. Общие указания")
    doc.para(f"Архитектурные решения объекта «{m.object_name}» разработаны в соответствии с заданием "
             f"на проектирование и действующими строительными нормами Республики Казахстан.")

    doc.heading("2. Объёмно-планировочные решения")
    a, b = (fmt_num(x, 1) for x in v.axes_m)
    basement = ", с техническим подвалом" if v.has_basement else ""
    doc.para(f"Здание {v.floors}-этажное{basement}, прямоугольное в плане, с размерами в осях {a} × {b} м. "
             f"Высота этажа — {fmt_num(v.floor_height_m, 1)} м.")
    doc.para(ctx.pick(
        "Расстановка мебели и технологического оборудования выполнена в соответствии с "
        "функциональным назначением помещений.",
        "Планировочные решения обеспечивают нормативные связи помещений и пути эвакуации.",
    ))
    t = TableRows()
    t.add([t.next_no, "Этажность", "этаж", ctx.fmt(S, "floors")], {"floors": 3})
    t.add([t.next_no, "Площадь застройки", "м²", ctx.fmt(S, "building_area_m2")], {"building_area_m2": 3})
    t.add([t.next_no, "Строительный объём", "м³", ctx.fmt(S, "construction_volume_m3")],
          {"construction_volume_m3": 3})
    doc.add_rows(["№ п/п", "Показатель", "Ед. изм.", "Значение"], t, [0.09, 0.55, 0.14, 0.22], "tbl_ar_tep")

    doc.heading("3. Экспликация помещений")
    t = TableRows()
    for floor in range(1, v.floors + 1):
        t.add(["", f"{floor} этаж", "", ""], bold=True)
        rooms = [r for r in v.rooms if r.floor == floor]
        for r in rooms:
            t.add([r.number, lex.ROOMS[r.kind], fmt_num(r.area_m2), r.category], {f"room.{r.number}.area_m2": 2})
        t.add(["", f"Итого по {floor} этажу", fmt_num(sum(r.area_m2 for r in rooms)), ""], bold=True)
    t.add(["", "Итого общая площадь здания", ctx.fmt(S, "explication_total_area_m2"), ""],
          {"explication_total_area_m2": 2}, bold=True)
    doc.add_rows(["№ пом.", "Наименование", "Площадь, м²", "Кат."], t, [0.12, 0.58, 0.18, 0.12],
                 "tbl_explication")

    doc.heading("4. Отделка помещений")
    doc.para("Внутренняя отделка выполняется в соответствии с ведомостью отделки помещений. "
             "Полы в санузлах и помещениях с влажным режимом — керамическая плитка.")
    return doc
