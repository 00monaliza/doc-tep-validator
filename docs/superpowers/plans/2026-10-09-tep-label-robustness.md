# Устойчивость извлечения ТЭП к незнакомым формулировкам — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** извлекатель ТЭП из ПЗ находит показатели под формулировками, которых нет в словаре, и это измерено на скрытых формулировках.

**Architecture:** генератор получает профили `v3-dev`/`v3-test`, где метки, единицы и фразы ТЭП берутся из замороженного словаря `heldout.py`. Извлекатель `tep_baseline.py` перестаёт сравнивать метки напрямую со словарём и спрашивает `LabelMatcher`. Матчер работает каскадом exact → fuzzy → embedding с проверкой единицы. Текст читается от «число + единица» к метке рядом. Ступени включаются параметром `stages`, это даёт абляцию.

**Tech Stack:** Python 3.12, `uv`, pytest, pdfplumber (через `src/ingestion/real.py`), `transformers`/`torch` (уже в зависимостях), модель `intfloat/multilingual-e5-small`.

**Spec:** `docs/superpowers/specs/2026-10-09-tep-label-robustness-design.md`

## Global Constraints

- Реальные документы обрабатываются только локально; во время работы сервиса и тестов модель грузится с `local_files_only=True`, сеть нужна только `scripts/fetch_models.py`.
- Интерфейс `extract(pages) -> Extraction` сохраняется; новые параметры только именованные с умолчаниями.
- Регрессия: `v2` — 100 % по слотам (P = R = 1) при ступенях по умолчанию; реальная ОПЗ — ≥ 8 верных слотов из 10 и 0 неверных.
- Код в `src/ner/`, `src/crossvalidation/`, `src/pipeline.py`, `api/` не импортирует и не упоминает `heldout`.
- Пороги подбираются только на `v3-dev` (seeds 1–50). `v3-test` (seeds 8000–8099) запускается один раз для итоговых цифр (задача 9).
- Словарь `tep_lexicon.json` остаётся единственным источником формулировок извлекателя; каждая запись с источником (`synthetic`, `dev:real_opz_zhbi2`, `general`).
- Стиль: ruff, длина строки 120, комментарии и docstring как в окружающем коде (английский в коде, русский в README/доках).
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Таблица экспликации или генплана с площадями, не являющимися ТЭП («Площадь участка», «Площадь озеленения», м²), не должна давать `building_area_m2`/`total_area_m2` — тест в задаче 6 (`test_site_area_rows_are_not_tep`).
2. Числа без единицы ТЭП в тексте («в ценах 2026 г.», «II степень») не становятся кандидатами — тест в задаче 6 (`test_numbers_without_tep_unit_are_ignored`).
3. В одном предложении площадь и объём с разными единицами: каждое число получает своё поле — тест в задаче 6 (`test_two_values_in_one_sentence`).
4. Модель эмбеддингов не скачана: сервис работает, в отчёте одно предупреждение, без падения — тест в задаче 8 (`test_unavailable_embedder_warns_once`).
5. Метка с латинскими двойниками и сокращениями в ячейке таблицы («Oбщ. площадь корпуса», латинская O) распознаётся, а ячейка-название здания («Здание котельной») — нет — тесты в задаче 7.

---

### Task 1: Словарь скрытых формулировок и защита от утечки

**Files:**
- Create: `src/synthesis/data/heldout.py`
- Create: `tests/test_heldout.py`

**Interfaces:**
- Produces: `HELDOUT: dict[str, dict[str, dict[str, dict[str, tuple[str, ...]]]]]` — `HELDOUT[lang][half][kind][key]`, `lang ∈ {"ru","kz"}`, `half ∈ {"dev","test"}`, `kind ∈ {"labels","units","templates"}`. Ключи `labels` — поля ТЭП; `units` — канонические единицы `m2, m3, floor, kKZT, month`; `templates` — `eng_construction_volume_m3`, `eng_total_area_m2`, `object_axes`.

- [ ] **Step 1: Write the failing test**

`tests/test_heldout.py`:

```python
"""Held-out TEP wordings (generator profile v3) must stay out of the extractor."""

from __future__ import annotations

import json
import string
from pathlib import Path

from src.ner.common.tep_baseline import squash
from src.synthesis.data.heldout import HELDOUT

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDERS = {
    "eng_construction_volume_m3": {"v"},
    "eng_total_area_m2": {"v"},
    "object_axes": {"name", "floors", "a", "b"},
}


def _strings(x) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [s for v in x.values() for s in _strings(v)]
    return [s for v in x for s in _strings(v)]


def _lexicon_labels() -> set[str]:
    data = json.loads((ROOT / "src/ner/data/tep_lexicon.json").read_text(encoding="utf-8"))
    labels = [s for spec in data["fields"].values() for key in ("table", "text", "text_number_first")
              for s in _strings(spec.get(key, {}))]
    labels += _strings(data.get("negatives", {}))
    return {squash(x) for x in labels}


def test_halves_have_same_keys_and_do_not_overlap():
    for lang in ("ru", "kz"):
        dev, test = HELDOUT[lang]["dev"], HELDOUT[lang]["test"]
        assert dev.keys() == test.keys() == {"labels", "units", "templates"}
        for kind in dev:
            assert dev[kind].keys() == test[kind].keys(), (lang, kind)
        overlap = {squash(x) for x in _strings(dev["labels"])} & {squash(x) for x in _strings(test["labels"])}
        assert not overlap, overlap


def test_heldout_labels_are_not_in_lexicon():
    lexicon = _lexicon_labels()
    for lang, halves in HELDOUT.items():
        for half, kinds in halves.items():
            leaked = [x for x in _strings(kinds["labels"]) if squash(x) in lexicon]
            assert not leaked, (lang, half, leaked)


def test_templates_keep_placeholders():
    for lang, halves in HELDOUT.items():
        for kinds in halves.values():
            for name, variants in kinds["templates"].items():
                for t in variants:
                    names = {f for _, f, _, _ in string.Formatter().parse(t) if f}
                    assert PLACEHOLDERS[name] <= names, (lang, name, t)
                    assert names <= PLACEHOLDERS[name] | {"gen", "gen_cap"}, (lang, name, t)


def test_extractor_does_not_import_heldout():
    paths = [*(ROOT / "src/ner").rglob("*.py"), *(ROOT / "src/crossvalidation").rglob("*.py"),
             ROOT / "src/pipeline.py", *(ROOT / "api").rglob("*.py")]
    offenders = [str(p) for p in paths if "heldout" in p.read_text(encoding="utf-8")]
    assert not offenders, offenders
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_heldout.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.synthesis.data.heldout'`

- [ ] **Step 3: Write the vocabulary**

`src/synthesis/data/heldout.py`:

```python
"""Held-out TEP wordings for generator profile v3 (RU/KZ).

Labels, unit spellings and sentence templates that the extractor's lexicon
(`src/ner/data/tep_lexicon.json`) does not contain. `dev` is for tuning the
extractor, `test` only for the final numbers; extractor code must never import
this module (tests/test_heldout.py). Written by the author of the extractor:
leakage is reduced (separate halves, committed before the extractor), not ruled out.
"""

HELDOUT = {
    "ru": {
        "dev": {
            "labels": {
                "floors": ("Число этажей", "Кол-во этажей надземной части", "Этажей, шт."),
                "building_area_m2": ("Пл. застройки", "Площадь, занятая зданием", "Застроенная площадь"),
                "total_area_m2": ("Общ. площадь здания", "Площадь здания общая", "Суммарная площадь помещений"),
                "construction_volume_m3": ("Объём здания строительный", "Строит. объём",
                                           "Объём строительный здания"),
                "underground_volume_m3": ("в т. ч. подземной части", "в том числе подземная часть здания"),
                "estimated_cost_ktg": ("Стоимость строительства по смете (с НДС)", "Сметная ст-ть, всего"),
                "construction_duration_months": ("Срок строительства",
                                                 "Нормативная продолжительность строительства"),
            },
            "units": {"m2": ("кв. м", "м кв."), "m3": ("куб. м", "м куб."), "floor": ("эт",),
                      "kKZT": ("тыс. тг",), "month": ("месяцев",)},
            "templates": {
                "eng_construction_volume_m3": ("Строительный объём {gen} принят {v} м³.",
                                               "Объём {gen} (строительный) равняется {v} куб. м."),
                "eng_total_area_m2": ("Площадь {gen} общая — {v} м².", "Общая пл. {gen} составит {v} кв. м."),
                "object_axes": ("{name}: этажей — {floors}, размеры в осях {a} × {b} м.",),
            },
        },
        "test": {
            "labels": {
                "floors": ("Кол. этажей", "Количество надземных этажей", "Число надземных этажей"),
                "building_area_m2": ("Площадь под застройку", "Пл. застр. здания", "Площадь, занимаемая зданием"),
                "total_area_m2": ("Общ. пл. здания", "Общая пл. помещений", "Площадь здания, всего"),
                "construction_volume_m3": ("Объём здания (строительный)", "Стр. объём", "Объём строения"),
                "underground_volume_m3": ("в т. ч. подземная часть", "из них подземная часть"),
                "estimated_cost_ktg": ("Стоимость строительства (с НДС), всего", "Сметная ст-ть строительства"),
                "construction_duration_months": ("Срок строительства, всего", "Продолж. строительства"),
            },
            "units": {"m2": ("м.кв.", "кв.м."), "m3": ("м.куб.", "куб.м."), "floor": ("этажей",),
                      "kKZT": ("тыс.тенге",), "month": ("мес",)},
            "templates": {
                "eng_construction_volume_m3": ("Объём строительный {gen}: {v} куб. м.",
                                               "Для {gen} строительный объём равен {v} м³."),
                "eng_total_area_m2": ("Общая площадь помещений {gen}: {v} кв. м.",
                                      "Для {gen} принята общая площадь {v} м²."),
                "object_axes": ("{name}: количество этажей — {floors}, размеры в осях {a} × {b} м.",),
            },
        },
    },
    "kz": {
        "dev": {
            "labels": {
                "floors": ("Қабаттар саны", "Жер үсті қабаттарының саны"),
                "building_area_m2": ("Салынған аудан", "Ғимарат алып жатқан аудан"),
                "total_area_m2": ("Ғимараттың жалпы алаңы", "Жалпы алаң"),
                "construction_volume_m3": ("Ғимарат көлемі (құрылыс)", "Құр. көлемі"),
                "underground_volume_m3": ("жерасты бөлігі қоса алғанда",),
                "estimated_cost_ktg": ("Құрылыстың сметалық бағасы (ҚҚС-пен)", "Сметалық құн, барлығы"),
                "construction_duration_months": ("Құрылыс мерзімі",),
            },
            "units": {"m2": ("кв. м",), "m3": ("куб. м",), "floor": ("қаб.",), "kKZT": ("мың тг",),
                      "month": ("айлар",)},
            "templates": {
                "eng_construction_volume_m3": ("{gen_cap} құрылыс көлемі {v} м³ болып қабылданды.",
                                               "{gen_cap} көлемі (құрылыс) {v} куб. м тең."),
                "eng_total_area_m2": ("{gen_cap} жалпы алаңы — {v} м².", "{gen_cap} {v} м² жалпы алаңы қабылданды."),
                "object_axes": ("{name}: қабат саны — {floors}, осьтер бойынша өлшемдері {a} × {b} м.",),
            },
        },
        "test": {
            "labels": {
                "floors": ("Қабаттар саны (жер үсті)", "Қабаттылық"),
                "building_area_m2": ("Салынған алаң", "Ғимарат астындағы аудан"),
                "total_area_m2": ("Жалпы алаңы", "Ғимарат ауданы (жалпы)"),
                "construction_volume_m3": ("Құрылыстық көлем", "Ғимараттың көлемі, құрылыс"),
                "underground_volume_m3": ("жер асты бөлігі",),
                "estimated_cost_ktg": ("Сметалық құны (ҚҚС қоса)",),
                "construction_duration_months": ("Құрылыс мерзімі, барлығы", "Салу ұзақтығы"),
            },
            "units": {"m2": ("ш. м.",), "m3": ("т. м.",), "floor": ("қабаттар",), "kKZT": ("мың. теңге",),
                      "month": ("ай.",)},
            "templates": {
                "eng_construction_volume_m3": ("{gen_cap} құрылыстық көлемі {v} куб. м құрайды.",
                                               "{gen_cap} {v} м³ құрылыстық көлемі есептелген."),
                "eng_total_area_m2": ("{gen_cap} жалпы алаңы {v} кв. м құрайды.",
                                      "{gen_cap} {v} м² жалпы алаң есептелген."),
                "object_axes": ("{name} — {floors} қабатты ғимарат, осьтерде {a} × {b} м.",),
            },
        },
    },
}
```

Note: in KZ `test`, `"Қабаттылық"` and `"Жалпы алаңы"` are new; check that the halves do not overlap after `squash` (`"Ғимараттың жалпы алаңы"` in dev and `"Жалпы алаңы"` in test are different strings; the test checks equality, not substrings).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_heldout.py -v`
Expected: 4 passed. If `test_heldout_labels_are_not_in_lexicon` fails, replace the leaked label in `heldout.py` with another wording; never edit `tep_lexicon.json` for this.

- [ ] **Step 5: Commit**

```bash
git add src/synthesis/data/heldout.py tests/test_heldout.py
git commit -m "Скрытые формулировки ТЭП (dev/test) и проверка, что они не попали в словарь

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Профили генератора `v3-dev` и `v3-test`

**Files:**
- Modify: `src/synthesis/context.py` (Ctx fields, `ocr_noise`)
- Modify: `src/synthesis/pz_objects.py` (`tep_table`, `summary_table`, `object_sections`)
- Modify: `src/synthesis/generator.py:1-20` (docstring), `:51` (`PROFILES`), `:156-170` (`generate_set`)
- Modify: `scripts/generate_synthetic.py:35`
- Modify: `src/evaluation/extraction_eval.py:35`
- Test: `tests/test_synthesis.py`

**Interfaces:**
- Consumes: `HELDOUT` (Task 1).
- Produces: `generate_set(..., profile="v3-dev" | "v3-test")`; `PROFILES = ("v1", "v2", "v3-dev", "v3-test")`; `ground_truth.json["profile"]` equals the profile string; `Ctx.held_label(fld) -> str | None`, `Ctx.held_unit(unit_text) -> str | None`, `Ctx.held_template(name) -> str | None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_synthesis.py` (it already has `load`, `body_text`, `generate_set`, `pytest`):

```python
@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_v3_changes_only_wording(tmp_path, lang):
    """Same seed in v2 and v3: same buildings, values and discrepancies; only TEP wording differs."""
    v2 = load(generate_set(lang, 11, tmp_path / "v2", scans=False, profile="v2"))
    v3 = load(generate_set(lang, 11, tmp_path / "v3", scans=False, profile="v3-dev"))
    assert v3["profile"] == "v3-dev"
    assert v3["objects"] == v2["objects"]
    assert v3["injected_types"] == v2["injected_types"]
    core = lambda recs: [(r["type"], r.get("object"), [(x.get("field"), x.get("value")) for x in r["refs"]])  # noqa: E731
                         for r in recs]
    assert core(v3["discrepancies"]) == core(v2["discrepancies"])
    values = lambda g: {f: e["value"] for f, e in g["tep"]["PZ"].items()}  # noqa: E731
    assert values(v3) == values(v2)


@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_v3_uses_heldout_labels(tmp_path, lang):
    from src.ner.common.tep_baseline import squash
    from src.synthesis.data.heldout import HELDOUT

    v2 = squash(body_text(generate_set(lang, 11, tmp_path / "v2", scans=False, profile="v2") / "text" / "PZ.pdf"))
    v3 = squash(body_text(generate_set(lang, 11, tmp_path / "v3", scans=False, profile="v3-dev") / "text" / "PZ.pdf"))
    labels = {squash(x) for v in HELDOUT[lang]["dev"]["labels"].values() for x in v}
    assert sum(lab in v3 for lab in labels) >= 3
    assert sum(lab in v2 for lab in labels) <= 1  # a held-out label may contain a v2 one, not the reverse


def test_ocr_noise_changes_one_spot():
    import random

    from src.synthesis.context import ocr_noise

    rng = random.Random(0)
    out = {ocr_noise("Площадь застройки здания", rng) for _ in range(50)}
    assert "Площадь застройки здания" not in out or len(out) > 1
    assert all(abs(len(x) - len("Площадь застройки здания")) <= 1 for x in out)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_synthesis.py -k "v3 or ocr_noise" -v`
Expected: FAIL — `AssertionError` in `generate_set` (`profile in PROFILES`) and `ImportError: cannot import name 'ocr_noise'`.

- [ ] **Step 3: Implement `Ctx` additions in `src/synthesis/context.py`**

Add after the `NORM_CODES` dict:

```python
OCR_NOISE_RATE = 0.2  # share of held-out labels with an OCR-like defect
# unit text used by the templates -> canonical unit of the held-out vocabulary
UNIT_CANON = {"м²": "m2", "м³": "m3", "этаж": "floor", "эт.": "floor", "қабат": "floor",
              "тыс. тенге": "kKZT", "мың теңге": "kKZT", "мес.": "month", "ай": "month"}
_OCR_SWAPS = {"щ": "ш", "ь": "ъ", "о": "o", "а": "a", "е": "e", "р": "p", "с": "c", "і": "i", "ы": "ьі"}


def ocr_noise(text: str, rng: random.Random) -> str:
    """One OCR-like defect: a look-alike letter (Cyrillic -> Latin), a lost space or a word split by a space."""
    op = rng.choice(("swap", "glue", "split"))
    if op == "swap":
        spots = [i for i, ch in enumerate(text) if ch.lower() in _OCR_SWAPS]
        if spots:
            i = rng.choice(spots)
            rep = _OCR_SWAPS[text[i].lower()]
            return text[:i] + (rep.upper() if text[i].isupper() else rep) + text[i + 1:]
    if op == "glue" and " " in text:
        i = rng.choice([i for i, ch in enumerate(text) if ch == " "])
        return text[:i] + text[i + 1:]
    words = text.split(" ")
    long = [i for i, w in enumerate(words) if len(w) >= 6]
    if not long:
        return text
    k = rng.choice(long)
    cut = rng.randint(2, len(words[k]) - 2)
    words[k] = words[k][:cut] + " " + words[k][cut:]
    return " ".join(words)
```

Add to `Ctx` after `vrng`:

```python
    heldout: dict | None = None  # profile v3: held-out wording (data/heldout.py), one half of one language
    hrng: random.Random | None = None  # profile v3 choices; a separate stream keeps v2 draws as they are
```

and methods after `pick`:

```python
    def held_label(self, fld: str) -> str | None:
        """A held-out label for a TEP field (sometimes with an OCR defect), or None outside profile v3."""
        variants = self.heldout["labels"].get(fld) if self.heldout else None
        if not variants:
            return None
        label = self.hrng.choice(variants)
        return ocr_noise(label, self.hrng) if self.hrng.random() < OCR_NOISE_RATE else label

    def held_unit(self, unit: str) -> str | None:
        """A held-out spelling of a template unit ('м²', 'эт.', 'мес.' …), or None."""
        variants = self.heldout["units"].get(UNIT_CANON.get(unit, "")) if self.heldout else None
        return self.hrng.choice(variants) if variants else None

    def held_template(self, name: str) -> str | None:
        variants = self.heldout["templates"].get(name) if self.heldout else None
        return self.hrng.choice(variants) if variants else None
```

- [ ] **Step 4: Use them in `src/synthesis/pz_objects.py`**

In `tep_table`, after the `cell = {...}` dict and before `t.add(...)`:

```python
        cell["label"] = ctx.held_label(fld) or cell["label"]
        cell["unit"] = ctx.held_unit(unit) or cell["unit"]
```

Add a helper above `summary_table`:

```python
def _summary_head(ctx: Ctx, fld: str, default: str) -> str:
    """Summary-table header 'label, unit'; held-out wording in profile v3."""
    label = ctx.held_label(fld)
    if label is None:
        return default
    unit = "м³" if fld.endswith("_m3") else "м²"
    return f"{label}, {ctx.held_unit(unit) or unit}"
```

In `summary_table` replace

```python
    header = _header(ctx, [h["no"], h["name"]] + [h[f] for f in fields])
```

with

```python
    header = _header(ctx, [h["no"], h["name"]] + [_summary_head(ctx, f, h[f]) for f in fields])
```

In `object_sections`:

```python
            doc.para(words["object_axes"].format(name=nom, floors=b.tep["floors"], a=a, b=bb))
```
becomes
```python
            axes = ctx.held_template("object_axes") or words["object_axes"]
            doc.para(axes.format(name=nom, floors=b.tep["floors"], a=a, b=bb))
```

```python
        header = _header(ctx, [hdr["name"]] + [hdr[f] for f in fields])
        t = TableRows()
        t.add([units["name"]] + [units[f] for f in fields])
```
becomes
```python
        header = _header(ctx, [hdr["name"]] + [ctx.held_label(f) or hdr[f] for f in fields])
        t = TableRows()
        t.add([units["name"]] + [ctx.held_unit(units[f]) or units[f] for f in fields])
```

and in the engineering loop

```python
        text, mentions = fill(rng.choice(words[f"eng_{f}"]), {"v": (value, key)}, gen=gen, gen_cap=_cap(gen))
```
becomes
```python
        template = rng.choice(words[f"eng_{f}"])
        template = ctx.held_template(f"eng_{f}") or template
        text, mentions = fill(template, {"v": (value, key)}, gen=gen, gen_cap=_cap(gen))
```

- [ ] **Step 5: Wire the profiles in `src/synthesis/generator.py`**

Import: `from src.synthesis.data.heldout import HELDOUT`.

```python
PROFILES = ("v1", "v2", "v3-dev", "v3-test")
```

In `generate_set` replace

```python
    vrng = random.Random(f"{lang}:{seed}:v2") if profile == "v2" else None
```
with
```python
    vrng = random.Random(f"{lang}:{seed}:v2") if profile != "v1" else None  # v3 = v2 + held-out wording
    heldout = HELDOUT[lang][profile.removeprefix("v3-")] if profile.startswith("v3-") else None
    hrng = random.Random(f"{lang}:{seed}:v3") if heldout else None
```

and

```python
    ctx = Ctx(lang, values, meta, random.Random(rng.getrandbits(32)), plan, vrng)
```
with
```python
    ctx = Ctx(lang, values, meta, random.Random(rng.getrandbits(32)), plan, vrng, heldout, hrng)
```

Docstring paragraph after the v2 description:

```
``v3-dev`` / ``v3-test`` are v2 with the TEP labels, unit spellings and some
sentences of the ПЗ taken from ``data/heldout.py`` (about one label in five with
an OCR-like defect). Their choices come from a third RNG stream, so values,
buildings and discrepancies of a seed are those of v2: only the wording differs.
```

- [ ] **Step 6: Fix the two `profile == "v2"` checks**

`scripts/generate_synthetic.py:35`:
```python
        return set(SYNTHETIC_TYPES if profile != "v1" else SYNTHETIC_TYPES_V1)
```

`src/evaluation/extraction_eval.py:35`:
```python
    if gt.get("profile", "v1") != "v1":
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_synthesis.py tests/test_heldout.py -v`
Expected: all pass (the existing v1/v2 tests must stay green — v2 output is unchanged because `held_*` return None without `heldout`).

- [ ] **Step 8: Commit**

```bash
git add src/synthesis scripts/generate_synthetic.py src/evaluation/extraction_eval.py tests/test_synthesis.py
git commit -m "Генератор: профили v3-dev и v3-test со скрытыми формулировками ТЭП

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Модуль словаря: исходные метки, отрицательные примеры, единицы

**Files:**
- Create: `src/ner/common/lexicon.py`
- Modify: `src/ner/common/tep_baseline.py:28-115` (move `squash`, `_flatten`, `Lexicon`, `load_lexicon`, `LEXICON_PATH` out; re-export)
- Modify: `src/ingestion/common/numbers.py` (unit pattern constants)
- Modify: `src/ner/data/tep_lexicon.json` (`negatives`, `_about`)
- Test: `tests/test_lexicon.py`

**Interfaces:**
- Produces (`src.ner.common.lexicon`, re-exported by `tep_baseline`): `squash(s) -> str`; `load_lexicon(path=LEXICON_PATH) -> Lexicon`; `Lexicon` with the old fields plus `raw_labels: dict[str, list[str]]` (field → table and text labels as written) and `negatives: list[str]`; `Lexicon.unit_of(text) -> str | None` (falls back to `numbers.normalize_unit`); `Lexicon.unit_in(text) -> str | None` (unit at the end of a header cell).
- Produces (`numbers`): `M2_IN_TEXT: str`, `M3_IN_TEXT: str` (regex sources used by `UNIT_IN_TEXT_RE`).

- [ ] **Step 1: Write the failing test**

`tests/test_lexicon.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lexicon.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ner.common.lexicon'`

- [ ] **Step 3: Expose unit patterns in `src/ingestion/common/numbers.py`**

Replace the `UNIT_IN_TEXT_RE` definition with:

```python
M2_IN_TEXT = r"[мm]\.?\s?[2²]|кв\.\s?[мm]\.?|[мm]\.?\s?кв\.?"
M3_IN_TEXT = r"[мm]\.?\s?[3³]|куб\.\s?[мm]\.?|[мm]\.?\s?куб\.?"
# the same forms, searchable inside text (followed by a non-letter)
UNIT_IN_TEXT_RE = re.compile(
    rf"(?<![^\W\d_])(?:(?P<m2>{M2_IN_TEXT})|(?P<m3>{M3_IN_TEXT}))(?![^\W\d_]|\d)",
    re.IGNORECASE,
)
```

- [ ] **Step 4: Create `src/ner/common/lexicon.py`**

Move from `tep_baseline.py` without changes: `LEXICON_PATH` (path becomes `Path(__file__).resolve().parents[1] / "data" / "tep_lexicon.json"` — same file), `squash`, `_flatten`, `Lexicon.field_of`, `is_total`, `is_units_row`. New and changed parts:

```python
"""TEP lexicon (``src/ner/data/tep_lexicon.json``): field labels, units, table header words.

The only source of TEP wordings for the extractors; every entry names its source.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from src.ingestion.common.numbers import normalize_unit

LEXICON_PATH = Path(__file__).resolve().parents[1] / "data" / "tep_lexicon.json"
_UNIT_TAIL_RE = re.compile(r"[,(]\s*([^,()]{1,12}?)\s*\)?\s*$")


def squash(s: str) -> str:
    """Case-, 'ё'-, space- and punctuation-insensitive form of a label."""
    return re.sub(r"[\W_]+", "", s.lower().replace("ё", "е"))


def _flatten(by_source: dict) -> list[str]:
    return [x for items in by_source.values() for x in items]


@dataclass(frozen=True, eq=False)  # hashed by identity (cached patterns)
class Lexicon:
    field_units: dict[str, str]
    table_labels: dict[str, list[str]]  # field -> squashed labels (all languages)
    text_labels: dict[str, list[str]]  # field -> labels as written
    number_first: dict[str, list[str]]  # field -> labels that follow the number
    units: dict[str, list[str]]  # canonical unit -> spellings
    number_headers: list[str]
    units_row: list[str]
    total_row: list[str]
    raw_labels: dict[str, list[str]]  # field -> table and text labels as written
    negatives: list[str]  # labels of quantities that are not TEP ("Площадь участка")

    # field_of, is_total, is_units_row: unchanged, moved from tep_baseline

    def unit_of(self, text: str) -> str | None:
        s = squash(text)
        if not s:
            return None
        for canon, spellings in self.units.items():
            if any(s == squash(u) for u in spellings):
                return canon
        return normalize_unit(text)

    def unit_in(self, text: str) -> str | None:
        """Unit named after a comma or in brackets at the end of a header: 'Площадь застройки, м²'."""
        m = _UNIT_TAIL_RE.search(text)
        return self.unit_of(m.group(1)) if m else None


@cache
def load_lexicon(path: Path = LEXICON_PATH) -> Lexicon:
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = data["fields"]

    def per_field(key: str, squashed: bool) -> dict[str, list[str]]:
        out = {}
        for fld, spec in fields.items():
            labels = [x for lang in spec.get(key, {}).values() for x in _flatten(lang)]
            labels = list(dict.fromkeys(squash(x) if squashed else x.lower() for x in labels))
            if labels:
                out[fld] = labels
        return out

    raw = {fld: list(dict.fromkeys(x for key in ("table", "text") for lang in spec.get(key, {}).values()
                                   for x in _flatten(lang)))
           for fld, spec in fields.items()}
    h = data["headers"]
    return Lexicon(
        field_units={f: spec["unit"] for f, spec in fields.items()},
        table_labels=per_field("table", True),
        text_labels=per_field("text", False),
        number_first=per_field("text_number_first", False),
        units={u: list(dict.fromkeys(_flatten(v))) for u, v in data["units"].items()},
        number_headers=_flatten(h["number"]),
        units_row=_flatten(h["units_row"]),
        total_row=_flatten(h["total_row"]),
        raw_labels={f: labs for f, labs in raw.items() if labs},
        negatives=_flatten(data.get("negatives", {})),
    )
```

In `tep_baseline.py` delete the moved code and add:

```python
from src.ner.common.lexicon import LEXICON_PATH, Lexicon, load_lexicon, squash  # noqa: F401  (re-exported)
```

Keep `import json`/`cache` only if still used (ruff will tell).

- [ ] **Step 5: Add negatives to `src/ner/data/tep_lexicon.json`**

Top-level key after `"headers"`:

```json
"negatives": {
  "general": ["Площадь участка", "Площадь земельного участка", "Площадь озеленения", "Площадь покрытий",
              "Площадь помещения", "Высота этажа", "Объём работ",
              "Учаскенің ауданы", "Көгалдандыру ауданы", "Жабындар ауданы", "Қабат биіктігі"]
}
```

and extend `_about`: `… 'dev:real_opz_zhbi2' = the one real development document, 'general' = common construction terms (negatives: quantities that are not TEP). …`

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_lexicon.py tests/test_heldout.py tests/test_rules_v0.py tests/test_numbers.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/ner/common/lexicon.py src/ner/common/tep_baseline.py src/ingestion/common/numbers.py src/ner/data/tep_lexicon.json tests/test_lexicon.py
git commit -m "Словарь ТЭП в отдельном модуле: исходные метки, отрицательные примеры, единица в заголовке

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `LabelMatcher` (ступень exact) и ступени в `extract`

**Files:**
- Create: `src/ner/common/label_match.py`
- Modify: `src/ner/common/tep_baseline.py` (`Candidate`, `Extraction`, `_horizontal_fields`, `_horizontal`, `_vertical`, `object_index`, `extract`)
- Modify: `src/ner/common/rules.py:44-52` (`Extraction.method`)
- Modify: `src/crossvalidation/report.py:43-51` (`pz_tep` passes method)
- Modify: `src/evaluation/extraction_eval.py` (`predicted_slots` uses `rank`; new `real_verdicts`)
- Modify: `scripts/eval_tep_extraction.py` (`run_real` uses `real_verdicts`)
- Test: `tests/test_label_match.py`, `tests/test_tep_extraction.py`

**Interfaces:**
- Consumes: `Lexicon`, `squash` (Task 3).
- Produces:
  - `label_match.METHODS = ("exact", "fuzzy", "embedding")`
  - `label_match.Match(field: str, score: float, method: str)` (frozen dataclass)
  - `label_match.LabelMatcher(lex, methods=METHODS, unit_check=True, embedder=None)`, `.match(text: str, unit: str | None = None, where: str = "table") -> Match | None`, `.warnings: list[str]`
  - `tep_baseline.STAGES = ("exact", "anchor", "fuzzy", "embedding")`
  - `tep_baseline.extract(pages, lex=None, stages=STAGES) -> Extraction`; `Extraction.warnings: list[str]`
  - `Candidate.method: str = "exact"`, `Candidate.score: float = 1.0`, `Candidate.rank -> tuple[int, int, float]`
  - `rules.Extraction.method: str = "exact"` (JSON of extractions)
  - `extraction_eval.real_verdicts(ex, ann) -> list[tuple[str, str, float, str]]` — (object, field, table value, `"ok"` | `"missing"` | `"wrong (<v>)"`)

- [ ] **Step 1: Write the failing tests**

`tests/test_label_match.py`:

```python
from src.ner.common.label_match import LabelMatcher, Match
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
```

`tests/test_tep_extraction.py`:

```python
"""Extractor regressions: profile v2 stays perfect, the real dev document does not get worse."""

from __future__ import annotations

import json

import pytest

from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path
from src.evaluation.extraction_eval import Scores, gold_slots, predicted_slots, real_verdicts
from src.ingestion.real import load_pages
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_label_match.py tests/test_tep_extraction.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ner.common.label_match'`, `ImportError: cannot import name 'STAGES'`.

- [ ] **Step 3: Create `src/ner/common/label_match.py` (exact stage)**

```python
"""Which TEP field a label names, also when the lexicon does not list it verbatim.

A cascade; a stage runs only if the previous ones are not confident:

* ``exact``: the longest lexicon label contained in the text, ignoring case,
  spaces and punctuation (the original baseline);
* ``fuzzy``: words normalised (Latin look-alikes, truncations such as «пл.»,
  «застр.») and compared by prefix with a one-edit tolerance; a field scores the
  IDF-weighted share of one of its labels found in the text;
* ``embedding``: cosine similarity of multilingual-e5-small embeddings to the
  lexicon labels; table cells only, and only if fuzzy saw some evidence.

If the unit of the value is known, only fields with that unit compete. Every
wording still comes from ``tep_lexicon.json``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.ner.common.lexicon import Lexicon, squash

METHODS = ("exact", "fuzzy", "embedding")
_LETTER_RE = re.compile(r"[^\W\d_]")


@dataclass(frozen=True)
class Match:
    field: str
    score: float
    method: str


class LabelMatcher:
    def __init__(self, lex: Lexicon, methods: tuple[str, ...] = METHODS, unit_check: bool = True,
                 embedder=None) -> None:
        self.lex, self.methods, self.unit_check = lex, tuple(methods), unit_check
        self._embedder = embedder
        self.warnings: list[str] = []
        text_extra = {f: [squash(x) for x in labs] for f, labs in lex.text_labels.items()}
        self._exact_labels = {
            "table": lex.table_labels,
            "text": {f: list(dict.fromkeys(lex.table_labels.get(f, []) + text_extra.get(f, [])))
                     for f in lex.field_units},
        }
        self._memo: dict[tuple[str, str | None, str], Match | None] = {}

    def match(self, text: str, unit: str | None = None, where: str = "table") -> Match | None:
        """Field named by `text` (a table cell, or the words next to a number when `where='text'`)."""
        key = (text, unit, where)
        if key not in self._memo:
            self._memo[key] = self._match(text, unit, where)
        return self._memo[key]

    def _allowed(self, unit: str | None) -> set[str]:
        if unit is None or not self.unit_check:
            return set(self.lex.field_units)
        return {f for f, u in self.lex.field_units.items() if u == unit}

    def _match(self, text: str, unit: str | None, where: str) -> Match | None:
        allowed = self._allowed(unit)
        if not allowed or not _LETTER_RE.search(text):
            return None
        return self._exact(text, allowed, where)

    def _exact(self, text: str, allowed: set[str], where: str) -> Match | None:
        s = squash(text)
        best, best_len = None, 0
        for fld in allowed:
            for lab in self._exact_labels[where].get(fld, ()):
                if lab and lab in s and len(lab) > best_len:
                    best, best_len = fld, len(lab)
        return Match(best, 1.0, "exact") if best else None
```

- [ ] **Step 4: Switch `tep_baseline.py` to the matcher**

Imports: `from src.ner.common.label_match import METHODS, LabelMatcher, Match`.

Constants after `PRIORITY`:

```python
STAGES = ("exact", "anchor", "fuzzy", "embedding")  # ablation order; extract() takes a prefix
```

`Candidate` gets two fields and `rank`:

```python
    method: str = "exact"  # label_match stage that named the field
    score: float = 1.0

    @property
    def priority(self) -> int:
        return PRIORITY[self.source]

    @property
    def rank(self) -> tuple[int, int, float]:
        """Lower wins: horizontal table < vertical table < text, then exact < fuzzy < embedding."""
        return PRIORITY[self.source], METHODS.index(self.method), -self.score
```

`Extraction` gets `warnings: list[str] = field(default_factory=list)`.

Replace `_horizontal_fields`, `_horizontal`, `_vertical`:

```python
def _horizontal_fields(table: PageTable, lex: Lexicon, matcher: LabelMatcher) -> tuple[int, dict[int, Match]] | None:
    """(header row index, column -> match) if a row among the first three names >= 2 fields.
    A column's unit comes from its header ('Площадь, м²') or from a units row right below."""
    for i, row in enumerate(table.rows[:3]):
        cells = table.header if i == 0 else row
        below = table.rows[i + 1] if i + 1 < len(table.rows) else []
        units = below if below and lex.is_units_row(_label(below)) else []
        cols = {}
        for c, cell in enumerate(cells):
            if not cell:
                continue
            unit = lex.unit_in(cell) or (lex.unit_of(units[c]) if c < len(units) else None)
            if m := matcher.match(cell, unit):
                cols[c] = m
        if len({m.field for m in cols.values()}) >= 2:
            return i, cols
    return None


def _horizontal(table: PageTable, lex: Lexicon, matcher: LabelMatcher, index: ObjectIndex, ctx: str | None,
                row_objects: dict[str, str]) -> list[tuple[str | None, str, Match, float, list[str]]]:
    """(object id, row label, match, value, row) for every data cell of a horizontal table."""
    found = _horizontal_fields(table, lex, matcher)
    if found is None:
        return []
    h, cols = found
    data_rows = []
    for row in table.rows[h + 1:]:
        label = _label(row)
        if (label and (lex.is_total(label) or lex.is_units_row(label))) or \
                not any(_value(row[c], m.field, lex) is not None for c, m in cols.items() if c < len(row)):
            continue
        data_rows.append((label, row))
    out = []
    for label, row in data_rows:
        named = index.mentioned(label) if label else set()
        if len(data_rows) == 1 and ctx is not None:
            obj = ctx  # a single-row table inside a building's section describes that building
        elif len(named) == 1:
            obj = next(iter(named))
        elif label and squash(label) in row_objects:
            obj = row_objects[squash(label)]
        else:
            obj = ctx
        for c, m in cols.items():
            v = _value(row[c], m.field, lex) if c < len(row) else None
            if v is not None:
                out.append((obj, label, m, v, row))
    return out


def _vertical(table: PageTable, lex: Lexicon, matcher: LabelMatcher) -> list[tuple[Match, float, list[str]]]:
    """(match, value, row) for a table with a column of TEP labels; a row's unit comes from the units column."""
    rows = table.rows
    n_cols = max(len(r) for r in rows)
    header = table.header
    skip, unit_col = set(), None
    for c in range(n_cols):
        head = header[c] if c < len(header) else ""
        cells = [r[c] for r in rows[1:] if c < len(r) and r[c]]
        if any(squash(head) == squash(h) for h in lex.number_headers):
            skip.add(c)
        elif cells and sum(lex.unit_of(x) is not None for x in cells) >= len(cells) / 2:
            skip.add(c)
            unit_col = c

    def unit(row: list[str]) -> str | None:
        return lex.unit_of(row[unit_col]) if unit_col is not None and unit_col < len(row) else None

    matches = {c: [matcher.match(r[c], unit(r)) if c < len(r) and r[c] else None for r in rows]
               for c in range(n_cols) if c not in skip}
    hits = {c: sum(m is not None for m in ms) for c, ms in matches.items()}
    if not hits:
        return []
    label_col = max(hits, key=lambda c: hits[c])
    if hits[label_col] < 2:
        return []
    skip.add(label_col)
    numeric = {c: sum(number_readings(r[c]) != () for r in rows[1:] if c < len(r))
               for c in range(n_cols) if c not in skip}
    if not numeric:
        return []
    value_col = max(numeric, key=lambda c: numeric[c])
    out = []
    for row, m in zip(rows, matches[label_col], strict=True):
        if m is not None and value_col < len(row) and (v := _value(row[value_col], m.field, lex)) is not None:
            out.append((m, v, row))
    return out
```

`object_index(pages, lex=None, matcher=None)`:

```python
    lex = lex or load_lexicon()
    matcher = matcher or LabelMatcher(lex, methods=("exact",), unit_check=False)
    ...
            rows = _horizontal(table, lex, matcher, empty, None, {})
```

`extract`:

```python
def extract(pages: list[Page], lex: Lexicon | None = None, stages: tuple[str, ...] = STAGES) -> Extraction:
    """TEP candidates and the chosen value per (object, field). `stages` is a prefix of STAGES (ablation)."""
    assert stages == STAGES[: len(stages)], stages
    lex = lex or load_lexicon()
    matcher = LabelMatcher(lex, methods=tuple(s for s in stages if s in METHODS), unit_check="anchor" in stages)
    index = object_index(pages, lex, matcher)
    names = {o.id: o.name for o in index.objects}
    row_objects = {squash(o.name): o.id for o in index.objects}
    pts = page_texts(pages, index)
    carried = [None] + [pt.ctx_after for pt in pts[:-1]]

    cands: list[Candidate] = []
    for page, pt, car in zip(pages, pts, carried, strict=True):
        for table in page.tables:
            ctx = pt.context_above(table.top, car)
            h_rows = _horizontal(table, lex, matcher, index, ctx, row_objects)
            for obj, _, m, v, row in h_rows:
                cands.append(Candidate(obj or PROJECT, m.field, v, "table_h", page.number,
                                       _row_quote(pt, row, ""), m.method, m.score))
            if not h_rows:
                for m, v, row in _vertical(table, lex, matcher):
                    cands.append(Candidate(ctx or PROJECT, m.field, v, "table_v", page.number,
                                           _row_quote(pt, row, ""), m.method, m.score))
    cands += _text(pts, index, lex)

    buildings = [o for o in names if o != PROJECT]
    if len(buildings) == 1:  # one building: the general values are its values
        for c in cands:
            if c.object == PROJECT:
                c.object = buildings[0]
    result = Extraction(names | {PROJECT: "Проект в целом"}, cands, warnings=matcher.warnings)
    for c in sorted(cands, key=lambda c: c.rank):
        result.slots.setdefault((c.object, c.field), c)
    return result
```

Update the module docstring's last paragraph:

```
Which field a label names is decided by ``label_match.LabelMatcher``; ``stages``
switches on its steps for the ablation (``exact`` alone is the original
baseline). When a field of an object is stated several times, a horizontal
table wins over a vertical table, any table wins over a sentence, and an exact
label over a fuzzy or embedded one.
```

- [ ] **Step 5: Carry `method` into the report**

`src/ner/common/rules.py`, `Extraction` after `evidence`:
```python
    method: str = "exact"  # how the TEP label was recognised (label_match stage)
```

`src/crossvalidation/report.py` `pz_tep`: the `Extraction(...)` call gets `method=c.method` as the last argument:
```python
            "table" if c.source.startswith("table") else "text", c.quote, method=c.method)
```

- [ ] **Step 6: `real_verdicts` in `src/evaluation/extraction_eval.py`**

Add (`ann` is what `load_annotation` returns):

```python
def real_verdicts(ex: Extraction, ann) -> list[tuple[str, str, float, str]]:
    """(object, field, table value, 'ok' | 'missing' | 'wrong (<v>)') for every TEP of an annotated real ПЗ."""
    omap = map_objects(ex.objects, ann.objects)
    pred = {(omap.get(o, o), f): c.value for (o, f), c in ex.slots.items()}
    out = []
    for obj, fields in ann.tep.items():
        for f, gold in fields.items():
            if f in ("page", "axes_m") or obj not in ("abk", "ceh") and f not in FIELDS:
                continue
            table_value = gold[0] if isinstance(gold, list) else gold  # first listed = table value
            got = pred.get((obj, f))
            verdict = "missing" if got is None else "ok" if abs(got - table_value) < 1e-6 else f"wrong ({got:g})"
            out.append((obj, f, table_value, verdict))
    return out
```

In `predicted_slots` replace the priority comparison so it follows the extractor's choice:

```python
    pred: dict[tuple[str, str], tuple[tuple, float]] = {}
    ...
        if slot not in pred or c.rank < pred[slot][0]:
            pred[slot] = (c.rank, c.value)
```

`scripts/eval_tep_extraction.py` `run_real`:

```python
def run_real(stages) -> None:
    for path in sorted(ANNOTATIONS_DIR.glob("*.json")):
        ann = load_annotation(path)
        if not source_path(ann).exists():
            continue
        print(f"\n== {ann.document_id} (dev document: the lexicon may contain its labels)")
        for obj, f, value, verdict in real_verdicts(extract(load_pages(source_path(ann)), stages=stages), ann):
            print(f"  {obj:<5} {f:<30} {value:>10g}  {verdict}")
```

(the `--stages` argument is added in Task 5; until then call `run_real(STAGES)` from `main`). Remove the now unused `map_objects` import if ruff flags it.

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_label_match.py tests/test_tep_extraction.py tests/test_pipeline.py tests/test_rules_v0.py -v`
Expected: all pass (the real-document test passes or is skipped).

Run: `uv run ruff check src scripts tests`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add src/ner src/crossvalidation/report.py src/evaluation/extraction_eval.py scripts/eval_tep_extraction.py tests/test_label_match.py tests/test_tep_extraction.py
git commit -m "LabelMatcher: классификатор меток ТЭП (ступень exact), ступени и способ в кандидатах

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Абляция в оценке и замер базы на `v3-dev`

**Files:**
- Modify: `scripts/eval_tep_extraction.py`
- Modify: `docs/superpowers/specs/2026-10-09-tep-label-robustness-design.md` (§6, measured bar)

**Interfaces:**
- Consumes: `extract(pages, stages=...)`, `STAGES` (Task 4); profiles `v3-dev`, `v3-test` (Task 2).
- Produces: CLI `--profile v2 v3-dev v3-test`, `--stages exact,anchor,...`, `--ablation`; JSON report `{"<profile>_<lang>": {"<stages joined by +>": {"ALL": [P, R, F1], "<field>": [...]}}}`.

- [ ] **Step 1: Rewrite `run_synthetic` and `main`**

```python
def stage_list(spec: str) -> tuple[str, ...]:
    stages = tuple(s for s in spec.split(",") if s)
    if stages != STAGES[: len(stages)]:
        raise argparse.ArgumentTypeError(f"stages must be a prefix of {','.join(STAGES)}")
    return stages


def run_synthetic(args) -> dict:
    prefixes = [STAGES[:i] for i in range(1, len(STAGES) + 1)] if args.ablation else [args.stages]
    report = {}
    with tempfile.TemporaryDirectory() as tmp:
        for profile in args.profile:
            for lang in args.lang:
                scores = {p: Scores() for p in prefixes}
                texts = {p: (Counter(), Counter(), Counter()) for p in prefixes}
                rx, ignored = Scores(), 0
                for seed in seeds(args.seeds):
                    set_dir = generate_set(lang, seed, Path(tmp) / profile, scans=False, profile=profile)
                    gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
                    pz = set_dir / "text" / "PZ.pdf"
                    gold, pages = gold_slots(gt), load_pages(pz)
                    for p in prefixes:
                        ex = extract(pages, stages=p)
                        pred, ign = predicted_slots(ex, gt, gold)
                        scores[p].add(pred, gold)
                        for acc, c in zip(texts[p], text_scores(ex, gt)[:3], strict=True):
                            acc.update(c)
                        ignored += ign if p == prefixes[-1] else 0
                    rx.add({("b1", f): v for f, v in regex_extract(pdf.extract_text(pz), lang).items()}, gold)

                last = prefixes[-1]
                print(f"\n== {profile} {lang}, seeds {args.seeds}, stages {'+'.join(last)}: slots (P R F1)")
                print(f"{'field':<30} {'gold':>5}  {'extractor':<17}  regex (one phrase)")
                for f in (*FIELDS, None):
                    b, r = scores[last].prf(f), rx.prf(f)
                    rx_s = fmt(*r[:3]) if f in (None, "total_area_m2", "building_area_m2") else "    —"
                    print(f"{f or 'ALL':<30} {b[3]:>5}  {fmt(*b[:3])}  {rx_s}")
                print(f"(building fields outside any building in multi-building sets, not scored: {ignored})")
                if args.ablation:
                    print(f"{'stages':<32} slots P R F1        sentences P R")
                rows = {}
                for p in prefixes:
                    tp, fp, fn = (sum(c.values()) for c in texts[p])
                    tp_ = tp / (tp + fp) if tp + fp else 0
                    tr_ = tp / (tp + fn) if tp + fn else 0
                    if args.ablation:
                        print(f"{'+'.join(p):<32} {fmt(*scores[p].prf()[:3])}   {tp_:5.2f} {tr_:5.2f}")
                    rows["+".join(p)] = {f or "ALL": scores[p].prf(f)[:3] for f in (*FIELDS, None)} | {
                        "sentences": [tp_, tr_]}
                report[f"{profile}_{lang}"] = rows
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", default="5001-5040")
    ap.add_argument("--lang", nargs="+", default=["ru", "kz"])
    ap.add_argument("--profile", nargs="+", default=["v2"], choices=PROFILES)
    ap.add_argument("--stages", type=stage_list, default=STAGES, help=f"prefix of {','.join(STAGES)}")
    ap.add_argument("--ablation", action="store_true", help="score every prefix of the stages")
    ap.add_argument("--real", action="store_true", help="evaluate on annotated real dev documents instead")
    ap.add_argument("--json", type=Path, help="write the slot scores here")
    args = ap.parse_args()
    if args.real:
        run_real(args.stages)
        return 0
    report = run_synthetic(args)
    if args.json:
        args.json.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0
```

Imports: `from src.ner.common.tep_baseline import STAGES, extract`, `from src.synthesis.generator import PROFILES, generate_set`. Update the docstring usage block:

```
    uv run python scripts/eval_tep_extraction.py --seeds 5001-5040 --lang ru kz --profile v2
    uv run python scripts/eval_tep_extraction.py --profile v3-dev --seeds 1-50 --ablation   # tuning
    uv run python scripts/eval_tep_extraction.py --profile v3-test --seeds 8000-8099 --ablation  # final, once
    uv run python scripts/eval_tep_extraction.py --real      # dev real document(s), if present
```

- [ ] **Step 2: Smoke-run**

Run: `uv run python scripts/eval_tep_extraction.py --profile v2 v3-dev --seeds 1-3 --ablation`
Expected: tables for `v2_ru`, `v2_kz`, `v3-dev_ru`, `v3-dev_kz`; on v2 every prefix shows `ALL 1.00 1.00 1.00`; on v3-dev the numbers are lower (all prefixes equal for now — later stages are not implemented yet).

- [ ] **Step 3: Measure the base on v3-dev and fix the bar**

Run: `uv run python scripts/eval_tep_extraction.py --profile v3-dev --seeds 1-50 --stages exact --json build/research/tep_v3dev_base.json`

Record `ALL` F1 for RU and KZ (`F_ru`, `F_kz`). In spec §6 replace the first bullet with:

```markdown
- База (ступень `exact`) на `v3-dev`, seeds 1–50: F1 по слотам RU <F_ru>, KZ <F_kz> (замер 2026-10-xx).
  Планка на `v3-test`: на каждом языке закрыть не меньше половины разрыва до 1,0, то есть
  F1 ≥ (1 + F_база) / 2: RU ≥ <(1+F_ru)/2>, KZ ≥ <(1+F_kz)/2>.
```

with the angle-bracket values replaced by the measured numbers (two decimals).

- [ ] **Step 4: Commit**

```bash
git add scripts/eval_tep_extraction.py docs/superpowers/specs/2026-10-09-tep-label-robustness-design.md
git commit -m "Оценка извлечения: профили v3, ступени и абляция; база на v3-dev и планка

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Ступень `anchor`: единица в таблицах и чтение текста от числа

**Files:**
- Modify: `src/ner/common/tep_baseline.py` (`_text_anchored`, `extract`)
- Test: `tests/test_tep_extraction.py`

**Interfaces:**
- Consumes: `LabelMatcher.match(text, unit, where="text")`, `numbers.M2_IN_TEXT`, `M3_IN_TEXT` (Tasks 3–4).
- Produces: with `"anchor"` in `stages`, sentence candidates come from `_text_anchored(pts, index, lex, matcher) -> list[Candidate]`; without it the legacy `_text` runs.

Table units are already passed to the matcher since Task 4; `unit_check="anchor" in stages` turns their check on.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tep_extraction.py`. The tests build `Page` objects directly; check the constructor in `src/ingestion/real.py` (`Page`, `TextLine`, `PageTable`) and adapt the helper if field names differ:

```python
from src.ingestion.real import Page, PageTable, TextLine


def _page(lines: list[str], tables: list[list[list[str]]] = ()) -> Page:
    text_lines = [TextLine(text=t, top=20.0 * i, bottom=20.0 * i + 10) for i, t in enumerate(lines)]
    page_tables = [PageTable(rows=rows, header=rows[0], bbox=(0, 900 + 100 * k, 500, 990 + 100 * k), top=900 + 100 * k)
                   for k, rows in enumerate(tables)]
    return Page(number=1, lines=text_lines, tables=page_tables, text="\n".join(lines))


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tep_extraction.py -k "sentence or kazakh or without_tep or site_area or colon" -v`
Expected: `test_label_with_colon_and_spaced_unit` FAILS (the legacy sentence regex stops at «:» and does not know «кв. м»). The other four may already pass through the legacy code — they pin behaviour the new code must keep. If the `_page` helper does not match the real `Page` constructor, fix the helper first (this is the only expected non-assertion failure).

- [ ] **Step 3: Implement `_text_anchored`**

In `tep_baseline.py` (imports: `from src.ingestion.common.numbers import M2_IN_TEXT, M3_IN_TEXT, NUMBER_RE, number_readings`):

```python
TEXT_WINDOW = 120  # characters searched for the label on each side of a number
TEXT_UNITS = ("m2", "m3", "kKZT", "month")  # floors: "3-этажное" patterns
EXTRA_UNIT_FORMS = {"m2": [M2_IN_TEXT], "m3": [M3_IN_TEXT]}
# end of a clause: sentence end before a capital letter, ';', or ', ' (a decimal comma has no space)
BOUNDARY_RE = re.compile(r"[.!?]\s+(?=[A-ZА-ЯЁӘҒҚҢӨҰҮҺІ])|;|,\s")


def _spelling(s: str) -> str:
    return re.escape(s.strip()).replace(r"\.", r"\.?\s?").replace(r"\ ", r"\s?")


@cache
def _anchor_re(lex: Lexicon) -> re.Pattern[str]:
    """A number followed by a TEP unit in any spelling; the unit's group is named by its canonical id."""
    groups = []
    for canon in TEXT_UNITS:
        forms = [_spelling(s) for s in sorted(lex.units.get(canon, ()), key=len, reverse=True)]
        groups.append(f"(?P<{canon}>{'|'.join(forms + EXTRA_UNIT_FORMS.get(canon, []))})")
    return re.compile(rf"(?P<num>{NUMBER_RE.pattern})\s*(?:{'|'.join(groups)})(?![^\W\d_]|\d)", re.IGNORECASE)


def _left_start(text: str, start: int, floor: int) -> int:
    lo = max(floor, start - TEXT_WINDOW)
    for b in BOUNDARY_RE.finditer(text, lo, start):
        lo = b.end()
    return lo


def _right_end(text: str, end: int) -> int:
    hi = min(len(text), end + TEXT_WINDOW)
    b = BOUNDARY_RE.search(text, end, hi)
    return b.start() if b else hi


def _text_anchored(pts: list[PageText], index: ObjectIndex, lex: Lexicon, matcher: LabelMatcher) -> list[Candidate]:
    """Sentence TEP read from the number: every 'number + TEP unit' is named by the words before it
    (or after it, Kazakh order), up to a clause boundary or the previous number."""
    out, seen = [], set()
    for pt in pts:
        text = pt.text.replace("ё", "е").replace("Ё", "Е")  # same length: offsets stay valid
        prev_end = 0
        for m in _anchor_re(lex).finditer(text):
            unit = next(k for k in TEXT_UNITS if m.group(k))
            s = m.start("num")
            lo = _left_start(text, s, prev_end)
            found, qs, qe = matcher.match(text[lo:s], unit, where="text"), lo, m.end()
            if found is None:
                hi = _right_end(text, m.end())
                found, qs, qe = matcher.match(text[m.end():hi], unit, where="text"), s, hi
            prev_end = m.end()
            if found is None or (pt.page, s) in seen:
                continue
            value = _value(m.group("num"), found.field, lex)
            if value is None:
                continue
            seen.add((pt.page, s))
            obj, _ = resolve(pt, index, qs, qe)
            out.append(Candidate(obj or PROJECT, found.field, value, "text", pt.page, pt.text[qs:qe].strip(),
                                 found.method, found.score))
        for fld, rx, _ in _text_patterns(lex):  # floors: "3-этажное", "2 қабатты"
            if lex.field_units[fld] != "floor":
                continue
            for m in rx.finditer(text):
                s = m.start("num")
                if (pt.page, s) in seen or (value := _value(m.group("num"), fld, lex)) is None:
                    continue
                seen.add((pt.page, s))
                obj, _ = resolve(pt, index, m.start(), m.end())
                out.append(Candidate(obj or PROJECT, fld, value, "text", pt.page, pt.text[m.start():m.end()]))
    return out
```

In `extract` replace `cands += _text(pts, index, lex)` with:

```python
    cands += _text_anchored(pts, index, lex, matcher) if "anchor" in stages else _text(pts, index, lex)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_tep_extraction.py tests/test_label_match.py tests/test_pipeline.py -v`
Expected: all pass, including `test_v2_slots_are_perfect[STAGES]`.

Run: `uv run python scripts/eval_tep_extraction.py --profile v2 v3-dev --seeds 1-50 --ablation`
Expected: v2 stays 1.00 for every prefix; on v3-dev `exact+anchor` ≥ `exact`. Note the numbers in the commit message.

Run: `uv run python scripts/eval_tep_extraction.py --real`
Expected (if the document is present): ≥ 8 `ok`, no `wrong`.

- [ ] **Step 5: Commit**

```bash
git add src/ner/common/tep_baseline.py tests/test_tep_extraction.py
git commit -m "Ступень anchor: ТЭП в тексте читаются от числа с единицей, проверка единицы

v3-dev (seeds 1-50), F1 по слотам: exact RU <…> KZ <…>; +anchor RU <…> KZ <…>.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Ступень `fuzzy`

**Files:**
- Modify: `src/ner/common/label_match.py`
- Test: `tests/test_label_match.py`

**Interfaces:**
- Produces: `label_match.tokens(text) -> list[tuple[str, bool]]`, `label_match.word_matches(token, abbrev, word) -> bool`, constants `FUZZY_MIN`, `FUZZY_MARGIN`, `NEGATIVE = "_negative"`; `LabelMatcher._fuzzy(text, allowed) -> tuple[Match | None, float]` (match, best evidence among real fields — used by Task 8).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_label_match.py` (examples are not from `heldout.py`):

```python
from src.ner.common.label_match import tokens, word_matches

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_label_match.py -v`
Expected: FAIL — `ImportError: cannot import name 'tokens'`.

- [ ] **Step 3: Implement**

In `label_match.py` (add `import math`):

```python
FUZZY_MIN = 0.75  # share of a label's (weighted) words found in the text; tuned on v3-dev
FUZZY_MARGIN = 0.2  # over the next field or a negative label
NEGATIVE = "_negative"  # pseudo-field of lexicon "negatives" ("Площадь участка")
HOMOGLYPHS = str.maketrans("aceopxyki", "асеорхукі")  # Latin letters OCR puts into Cyrillic words
SYMBOLS = {"s": "площадь", "v": "объем"}  # "S общ.", "V стр."
# a word, a contraction "кол-во" / "ст-ть", and a truncation dot
_TOKEN_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]{1,3}(?![^\W\d_]))?\.?")


def tokens(text: str) -> list[tuple[str, bool]]:
    """(normalised word, is a truncation): 'Пл.' -> ('пл', True), 'кол-во' -> ('кол', True)."""
    out = []
    for m in _TOKEN_RE.finditer(text):
        raw = m.group().lower()
        bare = raw.rstrip(".")
        if bare in SYMBOLS:  # before the look-alike mapping: Latin S, V
            out.append((SYMBOLS[bare], False))
            continue
        word = raw.translate(HOMOGLYPHS).replace("ё", "е")
        abbrev = word.endswith(".") or "-" in word
        word = word.split("-")[0].rstrip(".")
        if len(word) >= 2:
            out.append((word, abbrev))
    return out


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _one_edit(a: str, b: str) -> bool:
    """Levenshtein distance <= 1."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = _common_prefix(a, b)
    return a[i + 1:] == b[i + 1:] if len(a) == len(b) else a[i:] == b[i + 1:]


def word_matches(token: str, abbrev: bool, word: str) -> bool:
    """Same word up to inflection (shared prefix), one OCR edit, or a truncation of it."""
    if abbrev and len(token) >= 2 and word.startswith(token):
        return True
    cp, short = _common_prefix(token, word), min(len(token), len(word))
    if cp >= 4 or (cp >= 3 and cp >= short - 2):
        return True
    return short >= 5 and _one_edit(token, word)
```

In `LabelMatcher.__init__` add:

```python
        self._labels = [(f, ws) for f, labs in lex.raw_labels.items() for lab in labs
                        if (ws := [w for w, _ in tokens(lab)])]
        self._labels += [(NEGATIVE, ws) for lab in lex.negatives if (ws := [w for w, _ in tokens(lab)])]
        vocab = {w for _, ws in self._labels for w in ws}
        n = len(lex.field_units)
        df = {w: len({f for f, ws in self._labels if f != NEGATIVE and any(word_matches(w, False, x) for x in ws)})
              for w in vocab}
        self._weight = {w: math.log(1 + n / max(df[w], 1)) for w in vocab}  # rarer across fields = heavier
```

Add the method and extend `_match`:

```python
    def _fuzzy(self, text: str, allowed: set[str]) -> tuple[Match | None, float]:
        """(match, evidence): the best label coverage per field; evidence is the best among real fields."""
        toks = tokens(text)
        if not toks:
            return None, 0.0
        best: dict[str, float] = {}
        for f, words in self._labels:
            if f != NEGATIVE and f not in allowed:
                continue
            total = sum(self._weight[w] for w in words)
            hit = sum(self._weight[w] for w in words if any(word_matches(t, a, w) for t, a in toks))
            best[f] = max(best.get(f, 0.0), hit / total if total else 0.0)
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
        if not ranked or ranked[0][1] == 0:
            return None, 0.0
        (top_f, top), second = ranked[0], ranked[1][1] if len(ranked) > 1 else 0.0
        if top_f == NEGATIVE and top >= FUZZY_MIN:
            return None, 0.0  # a known non-TEP quantity: no embedding either
        evidence = max((s for f, s in ranked if f != NEGATIVE), default=0.0)
        if top_f != NEGATIVE and top >= FUZZY_MIN and top - second >= FUZZY_MARGIN:
            return Match(top_f, round(top, 3), "fuzzy"), evidence
        return None, evidence

    def _match(self, text: str, unit: str | None, where: str) -> Match | None:
        allowed = self._allowed(unit)
        if not allowed or not _LETTER_RE.search(text):
            return None
        if m := self._exact(text, allowed, where):
            return m
        if "fuzzy" not in self.methods:
            return None
        m, _ = self._fuzzy(text, allowed)
        return m
```

- [ ] **Step 4: Run tests, then the dev evaluation**

Run: `uv run pytest tests/test_label_match.py tests/test_tep_extraction.py -v`
Expected: all pass. If `test_fuzzy_reads_unseen_wordings` or `test_fuzzy_abstains_on_non_tep` fails, adjust `FUZZY_MIN`/`FUZZY_MARGIN` (not the tests), then re-check both tests and v2.

Run: `uv run python scripts/eval_tep_extraction.py --profile v2 v3-dev --seeds 1-50 --ablation`
Expected: v2 1.00 at every prefix; `exact+anchor+fuzzy` on v3-dev above `exact+anchor`.

Run: `uv run python scripts/eval_tep_extraction.py --real`
Expected: ≥ 8 `ok`, no `wrong`.

- [ ] **Step 5: Commit**

```bash
git add src/ner/common/label_match.py tests/test_label_match.py
git commit -m "Ступень fuzzy: сокращения, латинские двойники, опечатки, вес слов по полям

v3-dev (seeds 1-50), F1 по слотам +fuzzy: RU <…> KZ <…>.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Ступень `embedding`, загрузка модели и предупреждение в отчёте

**Files:**
- Create: `src/ner/common/label_embed.py`
- Create: `scripts/fetch_models.py`
- Modify: `src/ner/common/label_match.py`
- Modify: `src/pipeline.py:379-408` (`analyze_document`), `:434-494` (`analyze_package`)
- Test: `tests/test_label_match.py`

**Interfaces:**
- Produces: `label_embed.MODEL_ID = "intfloat/multilingual-e5-small"`; `label_embed.LabelEmbedder` with `.available() -> bool`, `.embed(texts: list[str]) -> torch.Tensor` (rows L2-normalised), `.error: str | None`; `label_embed.get_embedder() -> LabelEmbedder` (one per process); `label_match.EMBED_UNAVAILABLE: str`, `EMBED_MIN`, `EMBED_MARGIN`, `EMBED_EVIDENCE`.

- [ ] **Step 1: Download the model (the user approved this)**

`scripts/fetch_models.py`:

```python
"""Download the label-embedding model into the Hugging Face cache (once; the only step that needs network).

    uv run python scripts/fetch_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from huggingface_hub import snapshot_download  # noqa: E402

from src.ner.common.label_embed import MODEL_ID  # noqa: E402

if __name__ == "__main__":
    print(snapshot_download(MODEL_ID, allow_patterns=["*.json", "*.safetensors", "sentencepiece.bpe.model"]))
```

(`label_embed.py` from Step 3 must exist first: write Step 3's module, then run.)

Run: `uv run python scripts/fetch_models.py`
Expected: a path under `~/.cache/huggingface/hub/models--intfloat--multilingual-e5-small/snapshots/…` (≈ 470 МБ).

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_label_match.py`:

```python
import pytest
import torch

from src.ner.common.label_embed import get_embedder
from src.ner.common.label_match import EMBED_UNAVAILABLE

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
```

- [ ] **Step 3: Implement `src/ner/common/label_embed.py`**

```python
"""Sentence embeddings of TEP labels: multilingual-e5-small, from local files only.

The weights are fetched once by ``scripts/fetch_models.py``; at run time nothing
goes to the network (real documents never leave the machine).
"""

from __future__ import annotations

from functools import cache

MODEL_ID = "intfloat/multilingual-e5-small"


class LabelEmbedder:
    def __init__(self, model_id: str = MODEL_ID) -> None:
        self.model_id = model_id
        self._tok = self._model = None
        self.error: str | None = None
        self._cache: dict = {}  # text -> embedding

    def available(self) -> bool:
        if self._model is None and self.error is None:
            try:
                from transformers import AutoModel, AutoTokenizer

                self._tok = AutoTokenizer.from_pretrained(self.model_id, local_files_only=True)
                self._model = AutoModel.from_pretrained(self.model_id, local_files_only=True).eval()
            except Exception as e:  # weights not downloaded, broken cache
                self.error = f"{type(e).__name__}: {e}"
        return self._model is not None

    def embed(self, texts: list[str]):
        """L2-normalised mean-pooled embeddings, one row per text (cached per text)."""
        import torch

        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            batch = self._tok([f"query: {t}" for t in missing], padding=True, truncation=True, max_length=64,
                              return_tensors="pt")
            with torch.no_grad():
                hidden = self._model(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1).float()
            vecs = torch.nn.functional.normalize((hidden * mask).sum(1) / mask.sum(1), dim=-1)
            self._cache.update(zip(missing, vecs, strict=True))
        return torch.stack([self._cache[t] for t in texts])


@cache
def get_embedder() -> LabelEmbedder:
    return LabelEmbedder()
```

- [ ] **Step 4: Add the stage to `label_match.py`**

Constants:

```python
EMBED_MIN = 0.86  # cosine to the nearest lexicon label; tuned on v3-dev
EMBED_MARGIN = 0.02  # over the best label of another field or a negative
EMBED_EVIDENCE = 0.4  # fuzzy evidence needed before asking the model (keeps cell names like "Гараж" out)
EMBED_MAX_LEN = 80
EMBED_UNAVAILABLE = ("Модель для незнакомых названий показателей не найдена (scripts/fetch_models.py): "
                     "показатели распознаны по словарю и нечёткому сопоставлению.")
```

In `__init__` add:

```python
        self._prototypes = [(f, lab) for f, labs in lex.raw_labels.items() for lab in labs]
        self._prototypes += [(NEGATIVE, lab) for lab in lex.negatives]
```

Property and method:

```python
    @property
    def embedder(self):
        if self._embedder is None:
            from src.ner.common.label_embed import get_embedder

            self._embedder = get_embedder()
        return self._embedder

    def _embedding(self, text: str, allowed: set[str]) -> Match | None:
        if not self.embedder.available():
            if EMBED_UNAVAILABLE not in self.warnings:
                self.warnings.append(EMBED_UNAVAILABLE)
            return None
        vecs = self.embedder.embed([text] + [lab for _, lab in self._prototypes])
        sims = (vecs[1:] @ vecs[0]).tolist()
        best: dict[str, float] = {}
        for (f, _), s in zip(self._prototypes, sims, strict=True):
            if f == NEGATIVE or f in allowed:
                best[f] = max(best.get(f, -1.0), s)
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
        (top_f, top), second = ranked[0], ranked[1][1] if len(ranked) > 1 else -1.0
        if top_f != NEGATIVE and top >= EMBED_MIN and top - second >= EMBED_MARGIN:
            return Match(top_f, round(top, 3), "embedding")
        return None
```

`_match` tail becomes:

```python
        m, evidence = self._fuzzy(text, allowed)
        if m or "embedding" not in self.methods or where != "table":
            return m
        if evidence >= EMBED_EVIDENCE and len(text) <= EMBED_MAX_LEN:
            return self._embedding(text, allowed)
        return None
```

- [ ] **Step 5: Surface the warning in the report (`src/pipeline.py`)**

In `analyze_document`, after `ex = extract_pz(pages)`:
```python
        doc["_warnings"] = ex.warnings
```

In `analyze_package`, before the loop that deletes `_` keys:
```python
    for d in docs:
        warnings += [w for w in d.get("_warnings", []) if w not in warnings]
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_label_match.py tests/test_tep_extraction.py tests/test_pipeline.py -v`
Expected: all pass; `test_real_model_smoke` runs (model downloaded in Step 1).

Run: `uv run python scripts/eval_tep_extraction.py --profile v2 v3-dev --seeds 1-50 --ablation`
Expected: v2 1.00 at every prefix; the `+embedding` row on v3-dev ≥ `+fuzzy`. If precision drops on v2 or v3-dev, raise `EMBED_MIN` / `EMBED_EVIDENCE` first.

- [ ] **Step 7: Commit**

```bash
git add src/ner/common/label_embed.py src/ner/common/label_match.py scripts/fetch_models.py src/pipeline.py tests/test_label_match.py
git commit -m "Ступень embedding: multilingual-e5-small локально, предупреждение без модели

v3-dev (seeds 1-50), F1 по слотам +embedding: RU <…> KZ <…>.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Подбор порогов на dev, итог на test, README

**Files:**
- Modify: `src/ner/common/label_match.py` (constants only)
- Modify: `README.md`
- Create: `build/research/tep_v3_dev.json`, `build/research/tep_v3_test.json` (in `.gitignore` via `build/`; not committed)

**Interfaces:**
- Consumes: everything above. Produces no code interfaces.

- [ ] **Step 1: Tune on v3-dev only**

Grid over `FUZZY_MIN ∈ {0.65, 0.75, 0.85}`, `FUZZY_MARGIN ∈ {0.1, 0.2, 0.3}`, `EMBED_MIN ∈ {0.82, 0.86, 0.9}`, `EMBED_EVIDENCE ∈ {0.3, 0.4, 0.5}` — change the constants by hand or in a scratch script under the scratchpad that monkeypatches `src.ner.common.label_match` and calls `run_synthetic`. Criterion, in order: v2 seeds 1–50 stays P = R = 1 (RU and KZ); real document ≥ 8 ok and 0 wrong; then the highest mean F1 (RU, KZ) on `v3-dev` seeds 1–50 at the full stage list; ties → higher thresholds (more precise). Write the chosen values into `label_match.py`.

Run after setting them:
`uv run python scripts/eval_tep_extraction.py --profile v2 v3-dev --seeds 1-50 --ablation --json build/research/tep_v3_dev.json`
`uv run python scripts/eval_tep_extraction.py --real`
`uv run pytest`
Expected: all green; v2 1.00.

- [ ] **Step 2: Commit the thresholds**

```bash
git add src/ner/common/label_match.py
git commit -m "Пороги fuzzy и embedding подобраны на v3-dev

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 3: Run v3-test once**

Run: `uv run python scripts/eval_tep_extraction.py --profile v3-test v2 --seeds 8000-8099 --ablation --json build/research/tep_v3_test.json`

Do not change any constant after this run. Compare the full-stage `ALL` F1 per language with the bar recorded in spec §6.

- [ ] **Step 4: README**

In the section after the evaluation table of «MVP: веб-сервис сверки ТЭП» add a subsection with the measured numbers (replace `<…>` with values from `tep_v3_test.json`, two decimals):

```markdown
### Незнакомые формулировки ТЭП

Извлекатель ПЗ распознаёт метку показателя каскадом (`src/ner/common/label_match.py`): словарь →
нечёткое сопоставление (сокращения «пл.», «застр.», латинские двойники, опечатка в одну букву) →
эмбеддинги `intfloat/multilingual-e5-small` (только для ячеек таблиц и только при частичном совпадении
слов). Единица значения должна подходить полю, известные не-ТЭП («Площадь участка») отсекаются.
В тексте показатель читается от числа с единицей к словам рядом. Модель скачивается один раз:
`uv run python scripts/fetch_models.py`; без неё сервис работает и пишет предупреждение.

Проверка на скрытых формулировках: профиль генератора `v3-test` (`src/synthesis/data/heldout.py`,
формулировки, которых нет в словаре, ~20 % меток с искажениями как после OCR), seeds 8000–8099,
по 100 наборов на язык; пороги подбирались только на `v3-dev` (seeds 1–50). F1 по слотам:

| Ступени | RU | KZ |
|---|---|---|
| словарь (исходный извлекатель) | <…> | <…> |
| + чтение от числа с единицей | <…> | <…> |
| + нечёткое сопоставление | <…> | <…> |
| + эмбеддинги | <…> | <…> |

На `v2` (seeds 8000–8099) — <…> / <…>; на реальной ОПЗ — <…> из 10, ложных <…>.

Ограничение: скрытые формулировки и правила сокращений написал один автор. Утечку снижают раздельные
половины dev/test и то, что словарь `heldout.py` закоммичен раньше кода извлекателя, но не исключают.
Независимая проверка — формулировки из реальных ПЗ, которых автор не видел.
```

Also add `label_match.py`, `label_embed.py`, `lexicon.py` to the «Структура» block under `ner/common/`, and `fetch_models.py` to `scripts/`.

- [ ] **Step 5: Final check and commit**

Run: `uv run pytest && uv run ruff check src scripts tests`
Expected: all green.

```bash
git add README.md
git commit -m "README: извлечение ТЭП под незнакомыми формулировками, итог на v3-test

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

If the bar from spec §6 is not reached on a language, say so in README next to the table (which stage falls short and on which fields) instead of tuning on `v3-test`.
