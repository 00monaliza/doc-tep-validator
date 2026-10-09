import pytest
import torch

from src.ner.common.label_embed import get_embedder
from src.ner.common.label_match import EMBED_UNAVAILABLE, LabelMatcher, Match, tokens, word_matches
from src.ner.common.lexicon import load_lexicon


def matcher(**kw) -> LabelMatcher:
    return LabelMatcher(load_lexicon(), **kw)


def test_exact_is_the_old_field_of():
    m = matcher(methods=("exact",), unit_check=False)
    lex = load_lexicon()
    for text in ("Площадь застройки, м²", "Этажность", "Ғимараттың жалпы ауданы", "Строительный объем"):
        assert m.match(text).field == lex.field_of(text)
    assert m.match("Классная комната") is None
    assert m.match("1 247,79") is None


def test_unit_check_excludes_incompatible_fields():
    m = matcher(methods=("exact",))
    assert m.match("Площадь застройки", "m2") == Match("building_area_m2", 1.0, "exact")
    assert m.match("Площадь застройки", "m3") is None
    assert matcher(methods=("exact",), unit_check=False).match("Площадь застройки", "m3").field == "building_area_m2"


def test_text_labels_only_in_text():
    m = matcher(methods=("exact",))
    assert m.match("объём здания котельной равен", "m3", where="text").field == "construction_volume_m3"
    assert m.match("Объём", "m3") is None  # a bare 'объём' cell is not a TEP label in a table



FULL = ("exact", "fuzzy")


def test_tokens_mark_truncations_and_fix_lookalikes():
    assert tokens("Пл. застр.") == [("пл", True), ("застр", True)]
    assert tokens("кол-во") == [("кол", True)]
    assert tokens("Oбщая") == [("общая", False)]  # Latin O
    assert tokens("S общ.") == [("площадь", False), ("общ", True)]


def test_word_matching():
    assert word_matches("общей", False, "общая")
    assert word_matches("плошадь", False, "площадь")  # one OCR edit
    assert word_matches("пл", True, "площадь")
    assert not word_matches("стоимость", False, "строительный")
    assert not word_matches("пл", False, "площадь")  # without a dot it is not a truncation


def test_fuzzy_reads_unseen_wordings():
    m = matcher(methods=FULL)
    assert m.match("Пл. застр. корпуса", "m2").field == "building_area_m2"
    assert m.match("Oбщ. площадь корпуса", "m2").field == "total_area_m2"
    assert m.match("Кол-во этажей", None).field == "floors"
    assert m.match("Объём строительный здания", "m3").field == "construction_volume_m3"
    assert m.match("Пл. застр. корпуса", "m2").method == "fuzzy"


def test_fuzzy_abstains_on_non_tep():
    m = matcher(methods=FULL)
    assert m.match("Здание котельной") is None
    assert m.match("Площадь участка", "m2") is None
    assert m.match("Площадь", "m2") is None  # which area? ambiguous


ALL = ("exact", "fuzzy", "embedding")


class FakeEmbedder:
    """Fixed vectors: texts in `known` get their vector, everything else a vector orthogonal to all of them."""

    def __init__(self, known: dict[str, list[float]], ok: bool = True):
        self.known, self.ok, self.calls = known, ok, 0

    def available(self) -> bool:
        return self.ok

    def embed(self, texts):
        self.calls += 1
        dim = len(next(iter(self.known.values())))
        rows = [self.known.get(t, [0.0] * (dim - 1) + [1.0]) for t in texts]
        return torch.nn.functional.normalize(torch.tensor(rows), dim=-1)


def test_embedding_decides_when_fuzzy_is_unsure():
    # "Площадь под зданием": fuzzy sees area words but cannot choose between building and total area
    fake = FakeEmbedder({"Площадь под зданием": [1.0, 0.0, 0.0], "Площадь застройки": [1.0, 0.0, 0.0]})
    m = LabelMatcher(load_lexicon(), methods=ALL, embedder=fake)
    got = m.match("Площадь под зданием", "m2")
    assert got is not None and got.field == "building_area_m2" and got.method == "embedding"


def test_embedding_respects_negatives_and_units():
    fake = FakeEmbedder({"Площадь земли под зданием": [1.0, 0.0, 0.0], "Площадь участка": [1.0, 0.0, 0.0]})
    m = LabelMatcher(load_lexicon(), methods=ALL, embedder=fake)
    assert m.match("Площадь земли под зданием", "m2") is None  # nearest prototype is a negative
    assert m.match("Площадь под зданием", "m3") is None  # no m3 field is close


def test_no_embedding_without_fuzzy_evidence():
    fake = FakeEmbedder({"Классная комната": [1.0, 0.0], "Площадь застройки": [1.0, 0.0]})
    m = LabelMatcher(load_lexicon(), methods=ALL, embedder=fake)
    assert m.match("Классная комната") is None and fake.calls == 0


def test_unavailable_embedder_warns_once():
    m = LabelMatcher(load_lexicon(), methods=ALL, embedder=FakeEmbedder({"x": [1.0]}, ok=False))
    m.match("Площадь под зданием", "m2")
    m.match("Площадь под всем зданием", "m2")
    assert m.warnings == [EMBED_UNAVAILABLE]


@pytest.mark.skipif(not get_embedder().available(), reason="модель не скачана: scripts/fetch_models.py")
def test_real_model_smoke():
    m = LabelMatcher(load_lexicon(), methods=ALL)
    assert m.match("Площадь участка", "m2") is None
    got = m.match("Площадь под зданием", "m2")
    assert got is None or got.field in {"building_area_m2", "total_area_m2", "useful_area_m2"}
    assert m.warnings == []


class CountingEmbedder(FakeEmbedder):
    """Says every text is the same as every prototype; counts how often the matcher asks it."""

    def __init__(self):
        super().__init__({"x": [1.0]})

    def embed(self, texts):
        self.calls += 1
        return torch.ones(len(texts), 1)


def test_near_miss_words_do_not_match():
    assert not word_matches("застекления", False, "застройки")
    assert not word_matches("пола", False, "полезная")
    assert word_matches("общей", False, "общая")
    assert word_matches("этажей", False, "этажность")
    assert word_matches("ауданы", False, "аудан")


NON_TEP = [("Площадь застекления фасадов", "m2"), ("Площадь мест общего пользования", "m2"),
           ("Площадь общих коридоров", "m2"), ("Площадь пола", "m2"), ("Объём бетона", "m3"),
           ("Объём засыпки", "m3"), ("Объём резервуара", "m3"), ("V степень огнестойкости", "m3"),
           ("Количество квартир", None), ("Коэффициент застройки", None),
           ("Продолжительность отопительного периода", "month"), ("Стоимость оборудования", "kKZT"),
           ("Сметная стоимость проектных работ", "kKZT"), ("Пәтерлер саны", None)]


@pytest.mark.parametrize(("text", "unit"), NON_TEP)
def test_non_tep_rows_are_rejected_without_asking_the_model(text, unit):
    emb = CountingEmbedder()
    m = LabelMatcher(load_lexicon(), methods=ALL, embedder=emb)
    assert m.match(text, unit) is None
    assert emb.calls == 0


def test_negative_in_text_window_blocks_one_word_label():
    m = matcher(methods=FULL)
    assert m.match("Объём земляных работ составляет", "m3", where="text") is None
    assert m.match("Объём здания котельной равен —", "m3", where="text").field == "construction_volume_m3"
