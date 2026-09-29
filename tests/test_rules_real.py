"""Rule-based checks v0 and GT matching on hand-made pages (no real document content)."""

from __future__ import annotations

from src.crossvalidation.objects import discover_objects, page_texts, resolve
from src.crossvalidation.rules import run_rules
from src.evaluation.match import map_objects, match
from src.evaluation.schema import Finding
from src.ingestion.real import Page, PageTable, TextLine
from src.ner.common.taxonomy import DiscrepancyType as T

HEADER = ["Наименование", "Этажность", "Площадь застройки", "Строительный объем", "Общая площадь"]


def page(no, lines, tables=()):
    tl = [TextLine(t, 10.0 * i) for i, t in enumerate(lines)]
    return Page(no, "\n".join(lines), tl, list(tables))


def table(rows, top):
    return PageTable(rows, (0, top, 500, top + 5), rows[0])


def make_doc():
    t1 = table([HEADER, ["Склад", "1", "600,00", "3 600,00", "550,00"], ["ИТОГО", "", "600,00", "3 600,00", "550,00"]],
               30)
    t2 = table([HEADER, ["Бытовой блок", "2", "410,00", "2950,5", "700,00"], ["", "", "", "", "95,5"],
                ["Всего", "", "410,00", "2950,5", "790,00"]], 30)
    p1 = page(1, ["1. Общие данные", "Сейсмичность площадки строительства - 9 баллов.",
                  "3.1 Складской корпус", "Здание прямоугольное с размерами в осях 24,0х24,0м. Высота 6 м.",
                  "Склад 1 600,00 3 600,00 550,00", "ИТОГО 600,00 3 600,00 550,00"], [t1])
    p2 = page(2, ["3.2 Блок бытовых помещений", "Размерами в осях 12х36 м.",
                  "Бытовой блок 2 410,00 2950,5 700,00", "95,5", "Всего 410,00 2950,5 790,00",
                  "Район строительства с сейсмичностью 8 баллов.", "4. Сети",
                  "Строительный объем складского корпуса составляет 4 100,00 м3, водопотребление 5 м3/сут.",
                  "Общая площадь здания 990,00 м2."], [t2])
    return [p1, p2]


def test_objects_and_resolution():
    pages = make_doc()
    idx = discover_objects(pages)
    assert [(o.name, o.abbrev) for o in idx.objects] == [("Складской корпус", "СК"), ("Блок бытовых помещений", "ББП")]
    assert "корп" not in idx.objects[0].stems or "корп" not in idx.objects[1].stems
    pts = page_texts(pages, idx)
    text = pts[1].text
    pos = text.index("Строительный объем")
    assert resolve(pts[1], idx, pos, pos + 10) == ("obj1", "mention")  # after "4. Сети": only the mention helps
    pos = text.index("Общая площадь здания")
    assert resolve(pts[1], idx, pos, pos + 10)[0] is None


def test_rules_find_injected_problems():
    r = run_rules(make_doc())
    got = sorted((f.type.value, f.object, f.field) for f in r.findings)
    assert got == [
        ("GEOMETRY_INCONSISTENCY", "obj2", "building_area_m2"),  # 12 x 36 = 432 > 410
        ("PARAMETER_CONTRADICTION", "site", "seismicity_points"),  # 9 and 8
        ("TABLE_TOTAL_MISMATCH", "obj2", "total_area_m2"),  # 700 + 95,5 != 790
        ("TEP_CROSS_SECTION_MISMATCH", "obj1", "construction_volume_m3"),  # table 3 600 vs text 4 100
    ]
    seis = next(f for f in r.findings if f.type == T.PARAMETER_CONTRADICTION)
    assert {ref.value for ref in seis.refs} == {8, 9}
    row = next(m for m in r.mentions if m.value == 700.0)
    assert (row.object, row.how) == ("obj2", "row label")
    for f in r.findings:  # every quote is verbatim page text
        for ref in f.refs:
            assert ref.quote in " ".join(make_doc()[ref.page - 1].text.split())


def test_unresolved_values_are_logged_not_compared():
    r = run_rules(make_doc())
    assert any(u["value"] == 990.0 for u in r.unresolved)
    assert all(ref.value != 990.0 for f in r.findings for ref in f.refs)


def test_row_label_after_number_column():
    pages = make_doc()
    summary = table([["№", "Наименование", "Общая площадь, м²"], ["1", "Бытовой блок", "700,00"],
                     ["2", "Складской корпус", "550,00"], ["", "Итого", "1250,00"]], 300)
    summary.bbox = (0, 85, 500, 115)  # around the three text lines added below
    lines = [ln.text for ln in pages[0].lines] + ["1 Бытовой блок 700,00", "2 Складской корпус 550,00", "Итого 1250,00"]
    pages[0] = page(1, lines, pages[0].tables + [summary])
    r = run_rules(pages)
    got = {(m.object, m.value, m.how) for m in r.mentions if m.page == 1 and m.how == "row label"}
    assert got == {("obj2", 700.0, "row label"), ("obj1", 550.0, "row label")}


def _f(id_, type_, obj, pages, level="numeric"):
    return Finding(id=id_, level=level, type=type_, field="x", object=obj,
                   refs=[{"page": p, "quote": "q"} for p in pages])


def test_map_objects_and_match():
    omap = map_objects({"obj1": "Здание цеха", "obj2": "Административно-бытовой корпус", "site": "Площадка"},
                       {"abk": "Административно-бытовой корпус", "ceh": "Здание цеха", "site": "Площадка"})
    assert omap == {"obj1": "ceh", "obj2": "abk", "site": "site"}
    assert map_objects({"obj1": "Административно-бытовой корпус"}, {"abk": "АБК корпус"})["obj1"] == "abk"
    gt = [_f("R1", T.TABLE_TOTAL_MISMATCH, "ceh", [3]), _f("R2", T.TABLE_TOTAL_MISMATCH, "abk", [2]),
          _f("R3", T.COPY_PASTE_LABEL, "ceh", [3], level="artifact")]
    pred = [_f("P1", T.TABLE_TOTAL_MISMATCH, "obj1", [3, 4]), _f("P2", T.TABLE_TOTAL_MISMATCH, "obj2", [5])]
    res = match(gt, pred, omap)
    assert [(g.id, p.id) for g, p in res.pairs] == [("R1", "P1")]
    assert [g.id for g in res.missed] == ["R2", "R3"] and [p.id for p in res.false] == ["P2"]
    assert res.precision == 0.5 and res.recall == 1 / 3
    assert res.by_level()["artifact"] == {"found": 0, "missed": 1, "false": 0}
