"""Extractor regressions: profile v2 stays perfect, the real dev document does not get worse."""

from __future__ import annotations

import json

import pytest

from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path
from src.evaluation.extraction_eval import Scores, gold_slots, predicted_slots, real_verdicts
from src.ingestion.real import Page, PageTable, TextLine, load_pages
from src.ner.common.tep_baseline import STAGES, extract
from src.synthesis.generator import generate_set

V2_SEEDS = [7000, 7001, 7002, 7003]


@pytest.fixture(scope="module")
def v2_sets(tmp_path_factory):
    out = tmp_path_factory.mktemp("v2")
    return [generate_set(lang, seed, out, scans=False, profile="v2") for lang in ("ru", "kz") for seed in V2_SEEDS]


@pytest.mark.parametrize("stages", [STAGES[:1], STAGES])
def test_v2_slots_are_perfect(v2_sets, stages):
    scores = Scores()
    for set_dir in v2_sets:
        gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
        gold = gold_slots(gt)
        pred, _ = predicted_slots(extract(load_pages(set_dir / "text" / "PZ.pdf"), stages=stages), gt, gold)
        scores.add(pred, gold)
    p, r, _, n = scores.prf()
    assert n > 0 and p == 1.0 and r == 1.0, (stages, scores.fp, scores.fn)


def test_real_dev_document_does_not_regress():
    paths = sorted(ANNOTATIONS_DIR.glob("*.json"))
    anns = [a for a in map(load_annotation, paths) if source_path(a).exists()]
    if not anns:
        pytest.skip("реального документа нет в рабочей копии (data/real в .gitignore)")
    for ann in anns:
        verdicts = [v for *_, v in real_verdicts(extract(load_pages(source_path(ann))), ann)]
        assert verdicts.count("ok") >= 8, verdicts
        assert not [v for v in verdicts if v.startswith("wrong")], verdicts




def _page(lines: list[str], tables: list[list[list[str]]] = ()) -> Page:
    text_lines = [TextLine(text=t, top=20.0 * i) for i, t in enumerate(lines)]
    page_tables = [PageTable(rows=rows, bbox=(0, 900 + 100 * k, 500, 990 + 100 * k), header=rows[0])
                   for k, rows in enumerate(tables)]
    return Page(number=1, text="\n".join(lines), lines=text_lines, tables=page_tables)


def _text_values(pages, stages=STAGES) -> dict[str, float]:
    ex = extract(pages, stages=stages)
    return {c.field: c.value for c in ex.candidates if c.source == "text"}


def test_two_values_in_one_sentence():
    page = _page(["Проектом принята общая площадь здания 1 247,79 м² при строительном объёме 4 963,84 м³."])
    assert _text_values([page], STAGES[:2]) == {"total_area_m2": 1247.79, "construction_volume_m3": 4963.84}


def test_kazakh_number_before_label():
    page = _page(["Қазандық ғимаратының 1 124,98 м³ құрылыс көлемі жобада қабылданған."])
    assert _text_values([page], STAGES[:2]) == {"construction_volume_m3": 1124.98}


def test_numbers_without_tep_unit_are_ignored():
    page = _page(["Сметная стоимость определена в текущих ценах 2026 г., степень огнестойкости II."])
    assert _text_values([page], STAGES[:2]) == {}


def test_site_area_rows_are_not_tep():
    table = [["Наименование", "Ед. изм.", "Значение"],
             ["Площадь участка", "м²", "5 000,00"],
             ["Площадь озеленения", "м²", "1 200,00"],
             ["Площадь застройки", "м²", "512,40"],
             ["Строительный объём", "м³", "3 100,00"]]
    ex = extract([_page(["Генеральный план"], [table])])
    fields = {c.field: c.value for c in ex.candidates if c.source.startswith("table")}
    assert fields == {"building_area_m2": 512.4, "construction_volume_m3": 3100.0}


def test_label_with_colon_and_spaced_unit():
    page = _page(["Площадь застройки: 512,40 кв. м."])
    assert _text_values([page], STAGES[:2]) == {"building_area_m2": 512.4}


def test_table_rows_are_not_read_as_sentences():
    rows = [["№", "Показатель", "Значение", "Ед. изм."], ["1", "Площадь застройки", "512,40", "м²"],
            ["2", "Строительный объём", "3 100,00", "м³"]]
    lines = [TextLine("Технико-экономические показатели", 0.0), TextLine("1 Площадь застройки 512,40 м²", 905.0),
             TextLine("2 Строительный объём 3 100,00 м³", 925.0)]
    page = Page(1, "\n".join(ln.text for ln in lines), lines, [PageTable(rows, (0, 900, 500, 990), rows[0])])
    ex = extract([page])
    assert {c.field for c in ex.candidates if c.source.startswith("table")} == {"building_area_m2",
                                                                                 "construction_volume_m3"}
    assert [c for c in ex.candidates if c.source == "text"] == []


def test_kazakh_case_ending_on_unit_word():
    page = _page(["Құрылыстың сметалық құны 2026 жылғы ағымдағы бағамен ресурстық әдіспен анықталды және "
                  "12 % ҚҚС-ты қоса алғанда 596 709,301 мың теңгені құрайды."])
    assert _text_values([page], STAGES[:2]) == {"estimated_cost_ktg": 596709.301}
