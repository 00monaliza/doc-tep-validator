from src.ner.common.lexicon import load_lexicon
from src.ner.common.tep_baseline import load_lexicon as reexported


def test_reexport_is_the_same_object():
    assert reexported() is load_lexicon()


def test_units_in_any_spelling():
    lex = load_lexicon()
    assert lex.unit_of("м²") == "m2"
    assert lex.unit_of("м.кв.") == "m2"
    assert lex.unit_of("куб. м") == "m3"
    assert lex.unit_of("Этажность") is None


def test_unit_at_end_of_header():
    lex = load_lexicon()
    assert lex.unit_in("Площадь застройки, м²") == "m2"
    assert lex.unit_in("Строительный объём (м3)") == "m3"
    assert lex.unit_in("Этажность") is None
    assert lex.unit_in("Наименование, назначение") is None


def test_raw_labels_and_negatives():
    lex = load_lexicon()
    assert "Площадь застройки" in lex.raw_labels["building_area_m2"]
    assert "общая площадь" in lex.raw_labels["total_area_m2"]  # text labels too
    assert "Площадь участка" in lex.negatives
