# Детекторы несоответствий v1 — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** поймать в ПЗ четыре типа несоответствий, которые пропускают правила v0 (метод расчёта объёма, отметка против рельефа, подпись таблицы, параметры здания), и измерить это на синтетике.

**Architecture:** новый модуль `src/crossvalidation/rules_v1.py` запускается после правил v0 на тех же страницах и возвращает `Finding` той же схемы. Параметры здания описаны в словаре `src/ner/data/parameter_lexicon.json`. Генератор получает профиль `v4` (= `v2` + новые части ПЗ и ошибки, своя ветка RNG). `analyze_package(..., detectors="v0"|"v1")`: S1 закреплён на `"v0"` (поведение тега `protocol-v1`), S2 и сервис — `"v1"`.

**Tech Stack:** Python 3.12, `uv`, pytest, pdfplumber (через `src/ingestion/real.py`), fpdf2-генератор.

**Spec:** `docs/superpowers/specs/2026-10-09-discrepancy-detectors-v1-design.md`

## Global Constraints

- Реальные документы никуда не отправляются; LLM не используется.
- `v2` и `v3` генератора не меняются ни в одном байте (тест сравнивает `ground_truth.json`).
- S1 (`RulesSystem`, `detectors="v0"`) даёт те же слоты, что код на теге `protocol-v1`; E2/E3 не перезапускаются.
- Пороги новых детекторов подбираются на `v4` dev-seeds 1–50; test-seeds 9000–9099 запускаются один раз (задача 9).
- Все формулировки параметров — в `parameter_lexicon.json` с источником (`synthetic`, `dev:real_opz_zhbi2`), не в коде.
- Детектор, которому не хватает входов, молча не срабатывает; исключение в детекторе не роняет проверку (предупреждение).
- Стиль: ruff, длина строки 120; коммиты заканчиваются `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Предложение с отметкой рельефа («абсолютные отметки … от 314,75 до 315,04») не читается как отметка 0.000 здания — тест в задаче 4 (`test_relief_sentence_is_not_building_elevation`).
2. Сокращение с точкой внутри фразы об отмостке («бетонная кл. В 7.5, шириной 1000 мм») не обрывает фразу до ширины — тест в задаче 7 (`test_blind_area_width_after_class_abbreviation`).
3. Сводная таблица по нескольким зданиям в разделе здания не даёт `COPY_PASTE_LABEL` — тест в задаче 6 (`test_summary_table_is_not_a_label`).
4. Объём, честно посчитанный по наружному обмеру (V ≫ S × H_чист), не даёт `TEP_CALCULATION_METHOD` — тест в задаче 5 (`test_outer_volume_is_fine`).
5. Падение одного детектора не роняет проверку пакета — тест в задаче 8 (`test_failing_detector_becomes_warning`).

---

### Task 1: Закрепить S1 на `protocol-v1`, флаг `detectors`, система S2

**Files:**
- Create: `scripts/snapshot_s1.py`, `tests/data/s1_protocol_v1_slots.json`, `tests/test_protocol_s1.py`
- Modify: `src/pipeline.py` (`analyze_document`, `analyze_package`)
- Modify: `src/evaluation/systems.py` (`RulesSystem`, new `RulesSystemV1`)

**Interfaces:**
- Produces: `analyze_package(paths, detectors: str = "v1") -> dict`; `analyze_document(path, loc, detectors="v1")`; `RulesSystem.detectors = "v0"`, `RulesSystemV1(RulesSystem)` with `name = "S2"`, `detectors = "v1"`.

- [ ] **Step 1: Snapshot script**

`scripts/snapshot_s1.py` (runs in any checkout; uses only APIs that exist at `protocol-v1`):

```python
"""Slots of S1 on a few final seeds, to pin S1 to the frozen protocol (run on the protocol-v1 tag).

    uv run python scripts/snapshot_s1.py OUT.json
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.systems import RulesSystem  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402

SEEDS = (8000, 8001, 8002)

if __name__ == "__main__":
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for lang in ("ru", "kz"):
            for seed in SEEDS:
                d = generate_set(lang, seed, Path(tmp), scans=False, profile="v2")
                slots = RulesSystem().detect(sorted((d / "text").glob("*.pdf")), lang)
                out[f"{lang}_{seed}"] = sorted(list(s) for s in slots)
    Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
```

- [ ] **Step 2: Produce the reference on the tag**

```bash
git worktree add ../tep-protocol-v1 protocol-v1
cp scripts/snapshot_s1.py ../tep-protocol-v1/scripts/
mkdir -p tests/data
(cd ../tep-protocol-v1 && uv run python scripts/snapshot_s1.py ../doc-tep-validator/tests/data/s1_protocol_v1_slots.json)
git worktree remove --force ../tep-protocol-v1
```

Expected: `tests/data/s1_protocol_v1_slots.json` with 6 keys (`ru_8000` … `kz_8002`). The worktree held only a copied script, so `--force` loses nothing.

- [ ] **Step 3: Write the failing test**

`tests/test_protocol_s1.py`:

```python
"""S1 must stay the system measured in E2/E3 (tag protocol-v1); S2 is the service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.evaluation.systems import RulesSystem, RulesSystemV1
from src.synthesis.generator import generate_set

REF = json.loads((Path(__file__).parent / "data" / "s1_protocol_v1_slots.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", sorted(REF))
def test_s1_matches_protocol_v1(tmp_path, key):
    lang, seed = key.split("_")
    d = generate_set(lang, int(seed), tmp_path, scans=False, profile="v2")
    slots = RulesSystem().detect(sorted((d / "text").glob("*.pdf")), lang)
    assert sorted(list(s) for s in slots) == REF[key]


def test_s2_is_named_and_uses_v1():
    assert (RulesSystem.name, RulesSystem.detectors) == ("S1", "v0")
    assert (RulesSystemV1.name, RulesSystemV1.detectors) == ("S2", "v1")
```

- [ ] **Step 4: Run it**

Run: `uv run pytest tests/test_protocol_s1.py -q -p no:warnings`
Expected: FAIL — `ImportError: cannot import name 'RulesSystemV1'`. (If, after adding the class, `test_s1_matches_protocol_v1` still fails, S1 has drifted since the tag: the fix below must restore it.)

- [ ] **Step 5: Implement the flag**

`src/pipeline.py`:
- import `from src.ner.common.tep_baseline import STAGES` next to `PROJECT`;
- `def analyze_document(path: Path, loc: Locator, detectors: str = "v1") -> dict:` and in the ПЗ branch
  ```python
          ex = extract_pz(pages, stages=STAGES[:1] if detectors == "v0" else STAGES)
  ```
- `def analyze_package(paths: list[Path], detectors: str = "v1") -> dict:` with `assert detectors in ("v0", "v1")` and `analyze_document(Path(p), loc, detectors)`.

Module docstring, first bullet, append: «`detectors="v0"` reproduces the frozen research system S1 (exact lexicon extraction, rules v0); `"v1"` (default, the service) adds the robust extraction and ``crossvalidation.rules_v1``.»

`src/evaluation/systems.py`:

```python
class RulesSystem:
    """S1: the rule-based pipeline as frozen at protocol-v1 (exact extraction + checks v0 + cross-section engine)."""

    name = "S1"
    detectors = "v0"

    def detect(self, paths: list[Path], lang: str) -> set[Slot]:
        report = analyze_package(paths, detectors=self.detectors)
        return {slot(f["type"], f["field"]) for f in report["findings"] if f["verdict"] != "MATCH"}


class RulesSystemV1(RulesSystem):
    """S2: the service pipeline (robust TEP extraction + checks v0 + detectors v1)."""

    name = "S2"
    detectors = "v1"
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_protocol_s1.py tests/test_systems.py tests/test_pipeline.py -q -p no:warnings`
Expected: all pass. If a `test_s1_matches_protocol_v1[...]` fails, diff the slots and trace which change since the tag moved S1 (likely the TEP extractor or lexicon); make `detectors="v0"` reproduce the tag, do not regenerate the reference.

- [ ] **Step 7: Commit**

```bash
git add scripts/snapshot_s1.py tests/data/s1_protocol_v1_slots.json tests/test_protocol_s1.py src/pipeline.py src/evaluation/systems.py
git commit -m "S1 закреплена на protocol-v1, флаг detectors, система S2

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Словарь параметров здания

**Files:**
- Create: `src/ner/data/parameter_lexicon.json`, `src/ner/common/parameters.py`, `tests/test_parameters.py`

**Interfaces:**
- Produces: `parameters.load_parameters() -> dict[str, Parameter]` (cached); `Parameter(name, mention_re: re.Pattern, materials: dict[str, list[str]], has_width: bool, unit: str | None)`; `Parameter.material_in(text) -> str | None` (longest synonym wins); `parameters.width_mm(text) -> float | None` («шириной 1000 мм», «ені 1,5 м»); `parameters.height_m(text, pattern) -> float | None`.

- [ ] **Step 1: Write the failing test**

`tests/test_parameters.py`:

```python
from src.ner.common.parameters import load_parameters, width_mm


def test_parameters_loaded():
    p = load_parameters()
    assert {"blind_area", "roof", "clear_height", "floor_height"} <= set(p)


def test_longest_material_wins():
    blind = load_parameters()["blind_area"]
    assert blind.material_in("асфальтобетонная отмостка шириной 1,5м") == "asphalt"
    assert blind.material_in("Отмостка - бетонная кл. В 7.5, шириной 1000 мм") == "concrete"
    assert blind.material_in("Отмостка шириной 1 м") is None


def test_width_in_mm():
    assert width_mm("Отмостка - бетонная кл. В 7.5, шириной 1000 мм") == 1000
    assert width_mm("асфальтобетонная отмостка шириной 1,5м") == 1500
    assert width_mm("Отмостка — бетон, ені 1,2 м.") == 1200
    assert width_mm("Отмостка бетонная.") is None


def test_mentions():
    p = load_parameters()
    assert p["blind_area"].mention_re.search("Отмостка — бетон")
    assert p["roof"].mention_re.search("Ғимараттардың шатыры — жалпақ")
    assert not p["roof"].mention_re.search("Отмостка — бетон")
```

- [ ] **Step 2: Run** `uv run pytest tests/test_parameters.py -q` — Expected: FAIL, `ModuleNotFoundError: src.ner.common.parameters`.

- [ ] **Step 3: Lexicon** `src/ner/data/parameter_lexicon.json`:

```json
{
  "_about": "Building parameters for detectors v1 (src/crossvalidation/rules_v1.py). Every entry lists its source: 'synthetic' = generator profile v4 (src/synthesis), 'dev:real_opz_zhbi2' = the one real development document. Mentions and materials are matched case-insensitively as word prefixes; the longest material synonym in a phrase wins.",
  "parameters": {
    "blind_area": {
      "mention": {"ru": {"synthetic": ["отмостк"], "dev:real_opz_zhbi2": ["отмостк"]}, "kz": {"synthetic": ["отмостк"]}},
      "materials": {
        "concrete": {"ru": {"synthetic": ["бетонн"], "dev:real_opz_zhbi2": ["бетонн"]}, "kz": {"synthetic": ["бетон"]}},
        "asphalt": {"ru": {"synthetic": ["асфальтобетонн"], "dev:real_opz_zhbi2": ["асфальтобетонн"]}, "kz": {"synthetic": ["асфальтбетон"]}}
      },
      "width": true
    },
    "roof": {
      "mention": {"ru": {"synthetic": ["кровл"]}, "kz": {"synthetic": ["шатыр"]}},
      "materials": {
        "membrane": {"ru": {"synthetic": ["мембран"]}, "kz": {"synthetic": ["мембрана"]}},
        "bitumen": {"ru": {"synthetic": ["наплавляем", "рулонн"]}, "kz": {"synthetic": ["балқытылатын", "орама"]}},
        "profiled": {"ru": {"synthetic": ["профилированн"]}, "kz": {"synthetic": ["профильденген"]}}
      },
      "width": false
    },
    "clear_height": {
      "mention": {"ru": {"synthetic": ["в чистоте"], "dev:real_opz_zhbi2": ["высота помещени"]}, "kz": {"synthetic": ["таза биіктіг"]}},
      "unit": "m"
    },
    "floor_height": {
      "mention": {"ru": {"synthetic": ["высота этажа"]}, "kz": {"synthetic": ["қабат биіктіг"]}},
      "unit": "m"
    }
  }
}
```

- [ ] **Step 4: Module** `src/ner/common/parameters.py`:

```python
"""Building parameters (``src/ner/data/parameter_lexicon.json``): how they are mentioned and their values.

Used by ``crossvalidation.rules_v1``. Mentions and material synonyms are word prefixes; in a phrase the
longest material synonym wins ("асфальтобетонная" is asphalt, not concrete).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from src.ingestion.common.numbers import NUMBER_RE, number_readings

PARAMETERS_PATH = Path(__file__).resolve().parents[1] / "data" / "parameter_lexicon.json"
_WIDTH_RE = re.compile(rf"(?:ширин\w*|ені)\D{{0,15}}?(?P<num>{NUMBER_RE.pattern})\s*(?P<unit>мм|м)(?![^\W\d_])",
                       re.IGNORECASE)


def _words(by_lang: dict) -> list[str]:
    return list(dict.fromkeys(w.lower() for by_src in by_lang.values() for ws in by_src.values() for w in ws))


@dataclass(frozen=True, eq=False)
class Parameter:
    name: str
    mention_re: re.Pattern[str]
    materials: dict[str, list[str]]
    has_width: bool
    unit: str | None

    def material_in(self, text: str) -> str | None:
        low = text.lower().replace("ё", "е")
        best, best_len = None, 0
        for material, words in self.materials.items():
            for w in words:
                if re.search(rf"(?<![^\W\d_]){re.escape(w)}", low) and len(w) > best_len:
                    best, best_len = material, len(w)
        return best


@cache
def load_parameters(path: Path = PARAMETERS_PATH) -> dict[str, Parameter]:
    data = json.loads(path.read_text(encoding="utf-8"))["parameters"]
    out = {}
    for name, spec in data.items():
        words = _words(spec["mention"])
        mention = re.compile("|".join(rf"(?<![^\W\d_]){re.escape(w).replace(r'\ ', r'\s+')}\w*" for w in words),
                             re.IGNORECASE)
        materials = {m: _words(v) for m, v in spec.get("materials", {}).items()}
        out[name] = Parameter(name, mention, materials, bool(spec.get("width")), spec.get("unit"))
    return out


def width_mm(text: str) -> float | None:
    m = _WIDTH_RE.search(text)
    if not m or not (readings := number_readings(m.group("num"))):
        return None
    return round(readings[0] * (1000 if m.group("unit").lower() == "м" else 1), 1)
```

- [ ] **Step 5: Run** `uv run pytest tests/test_parameters.py -q` — Expected: 4 passed. Ruff clean.

- [ ] **Step 6: Commit** `git add src/ner/data/parameter_lexicon.json src/ner/common/parameters.py tests/test_parameters.py` — message «Словарь параметров здания (отмостка, кровля, высоты)».

---

### Task 3: Генератор, профиль `v4`

**Files:**
- Create: `src/synthesis/values_v4.py`, `src/synthesis/pz_v4.py`
- Modify: `src/synthesis/data/ru_lexicon.py`, `src/synthesis/data/kz_lexicon.py` (`PZ_V4`)
- Modify: `src/synthesis/context.py` (`Ctx.v4`), `src/synthesis/pz_objects.py` (`object_sections` hooks), `src/synthesis/templates_ru/pz.py`, `src/synthesis/templates_kz/pz.py`, `src/synthesis/generator.py`
- Modify: `src/ner/common/taxonomy.py` (`SYNTHETIC_TYPES_V4_EXTRA`)
- Test: `tests/test_synthesis.py`

**Interfaces:**
- Consumes: `PzPlan`, `Building`, `mention_key` (`values.py`).
- Produces: `PROFILES` + `"v4"`; `generate_set(..., profile="v4", inject_v4: set[DiscrepancyType] | None = None)`; ground truth records with fields `absolute_elevation_m` (object `site`), `construction_volume_m3` (type `TEP_CALCULATION_METHOD`), `object_label`, `blind_area`/`roof` (object `all`); mention keys `site:relief:relief_min_m`, `site:relief:relief_max_m`, `<b>:object_section:{absolute_elevation_m,clear_height_m,floor_height_m,blind_area,roof}`, `<b>:object_table:object_label`, `all:landscaping:{blind_area,roof}`. Categorical values are written as `"<material>"` (roof) or `"<material>, <width> мм"` (blind area).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_synthesis.py`):

```python
from src.ner.common.taxonomy import SYNTHETIC_TYPES_V4_EXTRA


@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_v4_keeps_v2_values(tmp_path, lang):
    v2 = load(generate_set(lang, 12, tmp_path / "v2", scans=False, profile="v2"))
    v4 = load(generate_set(lang, 12, tmp_path / "v4", scans=False, profile="v4", inject_v4=set()))
    assert v4["objects"] == v2["objects"]
    assert {f: e["value"] for f, e in v4["tep"]["PZ"].items()} == {f: e["value"] for f, e in v2["tep"]["PZ"].items()}
    assert [d["type"] for d in v4["discrepancies"]] == [d["type"] for d in v2["discrepancies"]]


@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_v4_injects_new_types_with_anchors(tmp_path, lang):
    # seed with at least two buildings so that a table label can name another building
    for seed in range(1, 40):
        set_dir = generate_set(lang, seed, tmp_path / str(seed), scans=False, profile="v4",
                               inject_v4=set(SYNTHETIC_TYPES_V4_EXTRA))
        gt = load(set_dir)
        if len(gt["objects"]) >= 2:
            break
    got = {(d["type"], d["field"]) for d in gt["discrepancies"]}
    assert ("TEP_CALCULATION_METHOD", "construction_volume_m3") in got or \
        not any(o["tep"]["floors"] == 1 for o in gt["objects"].values())
    assert ("VALUE_CROSS_SECTION_MISMATCH", "absolute_elevation_m") in got
    assert ("COPY_PASTE_LABEL", "object_label") in got
    assert got & {("PARAMETER_CONTRADICTION", "blind_area"), ("PARAMETER_CONTRADICTION", "roof")}
    text = norm(body_text(set_dir / "text" / "PZ.pdf"))
    for d in gt["discrepancies"]:
        for r in d["refs"]:
            assert r["anchors"], (d["type"], r["mention"])
            for a in r["anchors"]:
                assert norm(a["text"]) in text, (d["type"], a["text"])


def test_v2_and_v3_untouched_by_v4(tmp_path):
    for profile in ("v2", "v3-dev"):
        a = load(generate_set("ru", 13, tmp_path / f"a{profile}", scans=False, profile=profile))
        assert "absolute_elevation_m" not in json.dumps(a)
```

(Check the anchor field names in an existing `ground_truth.json` — `anchors[].text`; adapt the last assertion if the key differs.)

- [ ] **Step 2: Run** `uv run pytest tests/test_synthesis.py -k v4 -q -p no:warnings` — Expected: FAIL, `ImportError: cannot import name 'SYNTHETIC_TYPES_V4_EXTRA'`.

- [ ] **Step 3: Taxonomy** (`src/ner/common/taxonomy.py`, after `SYNTHETIC_TYPES_V2_EXTRA`):

```python
SYNTHETIC_TYPES_V4_EXTRA: tuple[DiscrepancyType, ...] = (
    DiscrepancyType.TEP_CALCULATION_METHOD,
    DiscrepancyType.VALUE_CROSS_SECTION_MISMATCH,
    DiscrepancyType.COPY_PASTE_LABEL,
    DiscrepancyType.PARAMETER_CONTRADICTION,  # blind area, roof (profile v4); v2 uses it for seismicity/fire
)
```

Do not add them to `SYNTHETIC_TYPES` (E3 sets stay as they are).

- [ ] **Step 4: Plan of v4 values** `src/synthesis/values_v4.py`:

```python
"""Profile v4: what the ПЗ of v2 does not state yet — site relief, building elevation 0.000, storey and clear
heights, blind area and roof — and four more discrepancy types. Drawn from its own RNG stream on top of a v2
plan, which stays untouched."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from src.ner.common.taxonomy import DiscrepancyType, Verdict
from src.synthesis.context import Ctx
from src.synthesis.values import PzPlan, mention_key

BLIND_MATERIALS = ("concrete", "asphalt")
BLIND_WIDTHS_MM = (800, 1000, 1200, 1500)
ROOFS = ("membrane", "bitumen", "profiled")
ELEVATION_SLACK_M = (0.15, 0.6)  # building 0.000 above the relief range
ELEVATION_JUMP_M = (20.0, 200.0)  # an elevation copied from another project


@dataclass
class V4Plan:
    values: dict[str, float | str]
    labels: dict[str, str]  # building id -> object name written in its ТЭП table ("" = its own name)
    discrepancies: list[dict] = field(default_factory=list)
    consistent_checks: list[dict] = field(default_factory=list)


def blind_value(material: str, width_mm: int) -> str:
    return f"{material}, {width_mm} мм"


def plan_v4(rng: random.Random, plan: PzPlan, floor_height_b1: float, inject: set[DiscrepancyType]) -> V4Plan:
    values: dict[str, float | str] = {}
    lo = round(rng.uniform(200, 900), 2)
    hi = round(lo + rng.uniform(0.3, 3.0), 2)
    values[mention_key("site", "relief", "relief_min_m")] = lo
    values[mention_key("site", "relief", "relief_max_m")] = hi
    blind_all = (rng.choice(BLIND_MATERIALS), rng.choice(BLIND_WIDTHS_MM))
    roof_all = rng.choice(ROOFS)
    values[mention_key("all", "landscaping", "blind_area")] = blind_value(*blind_all)
    values[mention_key("all", "landscaping", "roof")] = roof_all
    for b in plan.buildings:
        values[mention_key(b.id, "object_section", "absolute_elevation_m")] = round(
            rng.uniform(lo, hi) + rng.uniform(*ELEVATION_SLACK_M), 2)
        s, v, n = b.tep["building_area_m2"], b.tep["construction_volume_m3"], b.tep["floors"]
        if b.primary or not (s and v and n):
            fh = floor_height_b1
        else:
            fh = round((v / s - 0.5) / n, 2)  # inverse of values._aux_building
        values[mention_key(b.id, "object_section", "floor_height_m")] = fh
        values[mention_key(b.id, "object_section", "clear_height_m")] = round(fh - rng.uniform(0.3, 0.5), 2)
        values[mention_key(b.id, "object_section", "blind_area")] = blind_value(*blind_all)
        values[mention_key(b.id, "object_section", "roof")] = roof_all
    labels = {b.id: "" for b in plan.buildings}

    by_id = {b.id: b for b in plan.buildings}
    calc_target = None
    if DiscrepancyType.TEP_CALCULATION_METHOD in inject:
        ones = [b for b in plan.buildings if b.tep["floors"] == 1 and b.tep["building_area_m2"]
                and b.tep["construction_volume_m3"]]
        if ones:
            b = rng.choice(ones)
            calc_target = b.id
            values[mention_key(b.id, "object_section", "clear_height_m")] = round(
                b.tep["construction_volume_m3"] / b.tep["building_area_m2"], 2)  # V = S x clear height
    elevation_target = None
    if DiscrepancyType.VALUE_CROSS_SECTION_MISMATCH in inject:
        b = rng.choice(plan.buildings)
        elevation_target = b.id
        key = mention_key(b.id, "object_section", "absolute_elevation_m")
        values[key] = round(float(values[key]) + rng.choice((-1, 1)) * rng.uniform(*ELEVATION_JUMP_M), 2)
    label_target = None
    if DiscrepancyType.COPY_PASTE_LABEL in inject and len(plan.buildings) >= 2:
        b, other = rng.sample(plan.buildings, 2)
        label_target, labels[b.id] = b.id, other.id
    param_target = None
    if DiscrepancyType.PARAMETER_CONTRADICTION in inject:
        b = rng.choice(plan.buildings)
        param = rng.choice(("blind_area", "roof"))
        param_target = (b.id, param)
        key = mention_key(b.id, "object_section", param)
        if param == "roof":
            values[key] = rng.choice([r for r in ROOFS if r != roof_all])
        elif rng.random() < 0.5:
            values[key] = blind_value(rng.choice([m for m in BLIND_MATERIALS if m != blind_all[0]]), blind_all[1])
        else:
            values[key] = blind_value(blind_all[0], rng.choice([w for w in BLIND_WIDTHS_MM if w != blind_all[1]]))

    out = V4Plan(values, labels)

    def ref(obj: str, place: str, fld: str) -> dict:
        key = mention_key(obj, place, fld)
        return {"object": obj, "section": "PZ", "field": fld, "place": place, "value": values[key], "mention": key}

    def record(dtype: DiscrepancyType, obj: str, fld: str, refs: list[dict], mismatch: bool) -> None:
        rec = {"type": dtype.value, "object": obj, "field": fld, "refs": refs,
               "expected_verdict": (Verdict.MISMATCH if mismatch else Verdict.MATCH).value}
        (out.discrepancies if mismatch else out.consistent_checks).append(rec)

    relief = [ref("site", "relief", "relief_min_m"), ref("site", "relief", "relief_max_m")]
    for b in plan.buildings:
        record(DiscrepancyType.VALUE_CROSS_SECTION_MISMATCH, "site", "absolute_elevation_m",
               [ref(b.id, "object_section", "absolute_elevation_m")] + relief, b.id == elevation_target)
        if by_id[b.id].tep["construction_volume_m3"]:
            record(DiscrepancyType.TEP_CALCULATION_METHOD, b.id, "construction_volume_m3",
                   [ref(b.id, "object_table", "construction_volume_m3"), ref(b.id, "object_section", "clear_height_m")],
                   b.id == calc_target)
        if b.id == label_target:
            record(DiscrepancyType.COPY_PASTE_LABEL, b.id, "object_label",
                   [ref(b.id, "object_table", "object_label")], True)
        for param in ("blind_area", "roof"):
            record(DiscrepancyType.PARAMETER_CONTRADICTION, "all", param,
                   [ref(b.id, "object_section", param), ref("all", "landscaping", param)],
                   param_target == (b.id, param))
    return out
```

The label mention key `<b>:object_table:object_label` gets its value when rendering (the written name); `plan_v4` stores the other building's *id* in `labels`, rendering turns it into a name and writes `values[...]`. Add `values[mention_key(b.id, "object_table", "object_label")] = ""` for every building in `plan_v4` (filled during rendering) so anchoring checks cover it.

- [ ] **Step 5: Lexicons**

`ru_lexicon.py` (after `PZ_V2`):

```python
PZ_V4 = {
    "relief": ("Рельеф площадки спокойный, абсолютные отметки поверхности изменяются от {lo} м до {hi} м.",
               "Абсолютные отметки поверхности земли на участке — от {lo} м до {hi} м."),
    "elevation": ("За относительную отметку 0,000 принята отметка чистого пола первого этажа, что соответствует "
                  "абсолютной отметке {z}.",
                  "Относительная отметка 0,000 соответствует абсолютной отметке {z} м."),
    "heights": "Высота этажа — {fh} м, высота помещений в чистоте от пола до низа потолка {ch} м.",
    "blind_area": "Отмостка — {material} шириной {width}.",
    "roof": "Кровля — {roof}.",
    "landscaping_heading": "Благоустройство и общие конструктивные решения",
    "landscaping_blind_area": "Вокруг зданий выполняется {material} отмостка шириной {width}.",
    "landscaping_roof": "Кровля зданий — {roof}.",
    "materials": {"concrete": "бетонная", "asphalt": "асфальтобетонная"},
    "roofs": {"membrane": "плоская из ПВХ-мембраны", "bitumen": "плоская из наплавляемых рулонных материалов",
              "profiled": "скатная из профилированного листа"},
    "mm": "мм", "m": "м",
}
```

`kz_lexicon.py`:

```python
PZ_V4 = {
    "relief": ("Алаңның бедері тегіс, жер бетінің абсолюттік белгілері {lo} м-ден {hi} м-ге дейін өзгереді.",
               "Учаскедегі жер бетінің абсолюттік белгілері {lo} м-ден {hi} м-ге дейін."),
    "elevation": ("Салыстырмалы 0,000 белгісі ретінде бірінші қабаттың таза еденінің белгісі қабылданды, ол "
                  "{z} абсолюттік белгіге сәйкес келеді.",
                  "Салыстырмалы 0,000 белгісі {z} м абсолюттік белгіге сәйкес келеді."),
    "heights": "Қабат биіктігі — {fh} м, үй-жайлардың едені мен төбесі арасындағы таза биіктігі {ch} м.",
    "blind_area": "Отмостка — {material}, ені {width}.",
    "roof": "Шатыр — {roof}.",
    "landscaping_heading": "Абаттандыру және жалпы конструктивтік шешімдер",
    "landscaping_blind_area": "Ғимараттардың айналасында ені {width} {material} отмостка орындалады.",
    "landscaping_roof": "Ғимараттардың шатыры — {roof}.",
    "materials": {"concrete": "бетон", "asphalt": "асфальтбетон"},
    "roofs": {"membrane": "ПВХ-мембранадан жасалған жалпақ", "bitumen": "балқытылатын орама материалдардан жасалған жалпақ",
              "profiled": "профильденген табақтан жасалған еңісті"},
    "mm": "мм", "m": "м",
}
```

(KZ «таза биіктігі» must be matched by the lexicon prefix «таза биіктіг»; the KZ elevation puts the number before «абсолюттік белгі».)

- [ ] **Step 6: Rendering** `src/synthesis/pz_v4.py`:

```python
"""Profile v4 parts of the ПЗ (RU/KZ): relief, elevation 0.000, heights, blind area, roof, table labels."""

from __future__ import annotations

from types import ModuleType

from src.synthesis.context import Ctx
from src.synthesis.document import Document
from src.synthesis.formatting import fmt_num
from src.synthesis.pz_objects import fill, names
from src.synthesis.values import Building, mention_key


def _width(ctx: Ctx, width_mm: int, words: dict) -> str:
    if ctx.v4rng.random() < 0.5:
        return f"{width_mm} {words['mm']}"
    return f"{fmt_num(width_mm / 1000, 1)} {words['m']}"


def _blind(ctx: Ctx, value: str, words: dict) -> tuple[str, str]:
    material, width = value.split(", ")
    return words["materials"][material], _width(ctx, int(width.split()[0]), words)


def site_relief(ctx: Ctx, doc: Document, lex: ModuleType) -> None:
    v, words = ctx.v4.values, lex.PZ_V4
    lo_key, hi_key = mention_key("site", "relief", "relief_min_m"), mention_key("site", "relief", "relief_max_m")
    text, mentions = fill(ctx.v4rng.choice(words["relief"]),
                          {"lo": (fmt_num(v[lo_key], 2), lo_key), "hi": (fmt_num(v[hi_key], 2), hi_key)})
    doc.para(text, mentions)


def table_label(ctx: Ctx, lex: ModuleType, b: Building) -> str:
    """Object name in the building's ТЭП table: its own, or another building's (COPY_PASTE_LABEL)."""
    other = ctx.v4.labels[b.id]
    by_id = {x.id: x for x in ctx.plan.buildings}
    name = names(lex, by_id[other] if other else b)[0]
    ctx.v4.values[mention_key(b.id, "object_table", "object_label")] = name
    return name


def building_extras(ctx: Ctx, doc: Document, lex: ModuleType, b: Building) -> None:
    v, words = ctx.v4.values, lex.PZ_V4
    z_key = mention_key(b.id, "object_section", "absolute_elevation_m")
    text, mentions = fill(ctx.v4rng.choice(words["elevation"]), {"z": (fmt_num(v[z_key], 2), z_key)})
    doc.para(text, mentions)
    fh_key = mention_key(b.id, "object_section", "floor_height_m")
    ch_key = mention_key(b.id, "object_section", "clear_height_m")
    text, mentions = fill(words["heights"], {"fh": (fmt_num(v[fh_key], 2), fh_key),
                                             "ch": (fmt_num(v[ch_key], 2), ch_key)})
    doc.para(text, mentions)
    ba_key, roof_key = mention_key(b.id, "object_section", "blind_area"), mention_key(b.id, "object_section", "roof")
    material, width = _blind(ctx, str(v[ba_key]), words)
    text, mentions = fill(words["blind_area"], {"material": (material, ba_key)}, width=width)
    doc.para(text, mentions)
    text, mentions = fill(words["roof"], {"roof": (words["roofs"][v[roof_key]], roof_key)})
    doc.para(text, mentions)


def general_section(ctx: Ctx, doc: Document, lex: ModuleType, no: int) -> int:
    v, words = ctx.v4.values, lex.PZ_V4
    doc.heading(f"{no}. {words['landscaping_heading']}")
    ba_key, roof_key = mention_key("all", "landscaping", "blind_area"), mention_key("all", "landscaping", "roof")
    material, width = _blind(ctx, str(v[ba_key]), words)
    text, mentions = fill(words["landscaping_blind_area"], {"material": (material, ba_key)}, width=width)
    doc.para(text, mentions)
    text, mentions = fill(words["landscaping_roof"], {"roof": (words["roofs"][v[roof_key]], roof_key)})
    doc.para(text, mentions)
    return no + 1
```

Note: the blind-area anchor covers the material word; the width is part of the same sentence (the detector reads the sentence). Keep the ground-truth `value` canonical (`"asphalt, 1500 мм"`), anchors point at the material word.

- [ ] **Step 7: Wire it in**

`context.py` `Ctx`: add `v4: object | None = None` (the `V4Plan`) and `v4rng: random.Random | None = None` after `hrng`.

`pz_objects.object_sections`:
- data cell of the object table: `cells, pos = [pz_v4.table_label(ctx, lex, b) if ctx.v4 else nom], {}` and, when `ctx.v4`, `pos[mention_key(b.id, "object_table", "object_label")] = 0` (import `pz_v4` inside the function to avoid a cycle: `from src.synthesis import pz_v4`);
- after the seismicity paragraph of each building: `if ctx.v4: pz_v4.building_extras(ctx, doc, lex, b)`.

`templates_ru/pz.py` and `templates_kz/pz.py`:
- after `pz_objects.site_seismic(ctx, doc, lex)`: `if ctx.v4: pz_v4.site_relief(ctx, doc, lex)`;
- after `no = pz_objects.object_sections(ctx, doc, lex, no)`: `if ctx.v4: no = pz_v4.general_section(ctx, doc, lex, no)`.

`generator.py`:
- `PROFILES = ("v1", "v2", "v3-dev", "v3-test", "v4")`; v4 is v2-based: `vrng` for `profile != "v1"` already.
- signature `generate_set(..., profile="v2", inject_v4: set[DiscrepancyType] | None = None)`.
- after `plan = ...`:
  ```python
      v4 = None
      if profile == "v4":
          v4rng = random.Random(f"{lang}:{seed}:v4")
          if inject_v4 is None:
              inject_v4 = {t for t in SYNTHETIC_TYPES_V4_EXTRA if v4rng.random() < 0.5}
          v4 = plan_v4(v4rng, plan, values.floor_height_m, inject_v4)
  ```
  and `Ctx(..., heldout, hrng, v4, v4rng if v4 else None)`.
- after the v2 anchoring: `if v4: _check_anchored(v4.values, docs["PZ"]); discrepancies += _enrich_plan(v4.discrepancies, docs["PZ"]); checks += _enrich_plan(v4.consistent_checks, docs["PZ"])`, where `_check_anchored(values, pz)` is `_check_plan_anchored` generalised to a dict (make `_check_plan_anchored(plan, pz)` call it).
- `"injected_types": sorted({t.value for t in inject} | {t.value for t in (inject_v4 or set())})`.
- docstring: one paragraph on v4.

`plan_v4` must run before rendering and the `values` dict is filled for labels during rendering, so `_check_anchored` runs after `build`.

- [ ] **Step 8: Run tests**

Run: `uv run pytest tests/test_synthesis.py tests/test_heldout.py -q -p no:warnings`
Expected: all pass (existing v1/v2/v3 tests unchanged).

- [ ] **Step 9: Commit** — files above; message «Генератор: профиль v4 (рельеф, отметки, высоты, отмостка, кровля, подписи таблиц) и четыре типа ошибок».

---

### Task 4: Детектор «отметка и рельеф»

**Files:**
- Create: `src/crossvalidation/rules_v1.py`, `tests/test_rules_v1.py`

**Interfaces:**
- Produces: `rules_v1.ELEVATION_SLACK_M = 3.0`; `check_elevation(pts: list[PageText], index: ObjectIndex) -> list[Finding]` — one finding, object `site`, field `absolute_elevation_m`, `confidence="needs_expert"`, refs: each out-of-range building elevation and the relief statement(s).
- Test helper in `tests/test_rules_v1.py`: `_pages(*page_lines: list[str]) -> list[Page]` (one `Page` per argument, lines at `top = 20 * i`, no tables) and `_ctx(pages)` returning `(object_index(pages), page_texts(pages, index))`.

- [ ] **Step 1: Failing tests** `tests/test_rules_v1.py`:

```python
from __future__ import annotations

from src.crossvalidation.objects import page_texts
from src.crossvalidation.rules_v1 import check_elevation
from src.ingestion.real import Page, PageTable, TextLine
from src.ner.common.tep_baseline import object_index


def _page(no: int, lines: list[str], tables: list[PageTable] = ()) -> Page:
    text_lines = [TextLine(t, 20.0 * i) for i, t in enumerate(lines)]
    return Page(no, "\n".join(lines), text_lines, list(tables))


def _pages(*pages: list[str]) -> list[Page]:
    return [_page(i, lines) for i, lines in enumerate(pages, start=1)]


def _ctx(pages):
    index = object_index(pages)
    return index, page_texts(pages, index)


TWO_BUILDINGS = ["5. Объёмно-планировочные решения", "5.1 Здание офиса", "5.2 Здание цеха"]


def test_elevation_outside_relief():
    pages = _pages(["Рельеф площадки спокойный, абсолютные отметки поверхности изменяются от 314,75 м до 315,04 м."],
                   ["5.1 Здание офиса",
                    "Относительная отметка 0,000 соответствует абсолютной отметке - 489,79."])
    index, pts = _ctx(pages)
    found = check_elevation(pts, index)
    assert len(found) == 1 and found[0].object == "site" and found[0].field == "absolute_elevation_m"
    assert {r.value for r in found[0].refs} >= {489.79}


def test_elevation_inside_relief_is_fine():
    pages = _pages(["Абсолютные отметки поверхности земли на участке — от 314,75 м до 315,04 м."],
                   ["5.1 Здание офиса", "Относительная отметка 0,000 соответствует абсолютной отметке 315,30 м."])
    index, pts = _ctx(pages)
    assert check_elevation(pts, index) == []


def test_relief_sentence_is_not_building_elevation():
    pages = _pages(["5.1 Здание офиса",
                    "Абсолютные отметки поверхности изменяются от 314,75 м до 315,04 м."])
    index, pts = _ctx(pages)
    assert check_elevation(pts, index) == []  # no building elevation at all: nothing to compare


def test_kazakh_elevation_and_relief():
    pages = _pages(["Учаскедегі жер бетінің абсолюттік белгілері 314,75 м-ден 315,04 м-ге дейін."],
                   ["5.1 Қазандық ғимараты", "Салыстырмалы 0,000 белгісі 512,40 м абсолюттік белгіге сәйкес келеді."])
    index, pts = _ctx(pages)
    assert len(check_elevation(pts, index)) == 1
```

- [ ] **Step 2: Run** — Expected: FAIL, `ModuleNotFoundError: src.crossvalidation.rules_v1`.

- [ ] **Step 3: Implement** `src/crossvalidation/rules_v1.py`:

```python
"""Rule-based checks v1 for real documents, run after v0 (``rules.py``) on the same pages.

* ``VALUE_CROSS_SECTION_MISMATCH`` (``absolute_elevation_m``) — elevation 0.000 of a building outside the
  site relief range;
* ``TEP_CALCULATION_METHOD`` (``construction_volume_m3``) — volume equal to building area x clear height, or an
  implausibly low average storey height;
* ``COPY_PASTE_LABEL`` (``object_label``) — the ТЭП table of building X names another building;
* ``PARAMETER_CONTRADICTION`` (``blind_area``, ``roof``) — one building parameter stated differently;
  parameters come from ``ner/data/parameter_lexicon.json``.

Like v0, nothing here knows the concrete document; a check without its inputs does not fire.
"""

from __future__ import annotations

import re

from src.crossvalidation.objects import ObjectIndex, PageText, resolve
from src.crossvalidation.rules import _finding, _quote
from src.evaluation.schema import Finding, Ref
from src.ingestion.common.numbers import NUMBER_RE, number_readings
from src.ner.common.taxonomy import DiscrepancyType

ELEVATION_SLACK_M = 3.0  # a building rarely sits higher above (or below) the relief than this
_N = rf"(?P<{{}}>{NUMBER_RE.pattern})"
Z_RE = [
    re.compile(rf"абсолютн\w*\s+отметк\w*\s*[-–—:=]?\s*{_N.format('z')}", re.IGNORECASE),
    re.compile(rf"{_N.format('z')}\s*м?\s+абсолютт\w*\s+белгі", re.IGNORECASE),
]
RELIEF_RE = [
    re.compile(rf"отметк\w*[^.;]{{0,80}}?от\s+{_N.format('lo')}\s*м?\s*до\s+{_N.format('hi')}", re.IGNORECASE),
    re.compile(rf"белгілер\w*[^.;]{{0,40}}?{_N.format('lo')}\s*м?-?(?:ден|дан|тен|тан)\s+{_N.format('hi')}",
               re.IGNORECASE),
]


def _num(text: str) -> float | None:
    readings = number_readings(text)
    return readings[0] if readings else None


def _object(pt: PageText, index: ObjectIndex, start: int, end: int) -> str | None:
    obj, _ = resolve(pt, index, start, end)
    if obj is None and len(index.objects) == 1:
        return index.objects[0].id
    return obj


def check_elevation(pts: list[PageText], index: ObjectIndex) -> list[Finding]:
    relief: list[Ref] = []
    for pt in pts:
        for rx in RELIEF_RE:
            for m in rx.finditer(pt.text):
                lo, hi = _num(m.group("lo")), _num(m.group("hi"))
                if lo is not None and hi is not None:
                    relief.append(Ref(page=pt.page, quote=_quote(pt.text, m.group()), object="site",
                                      value=[min(lo, hi), max(lo, hi)], unit="m"))
    if not relief:
        return []
    lo = min(r.value[0] for r in relief)
    hi = max(r.value[1] for r in relief)
    outside: list[Ref] = []
    for pt in pts:
        for rx in Z_RE:
            for m in rx.finditer(pt.text):
                z = _num(m.group("z"))
                obj = _object(pt, index, m.start(), m.end())
                if z is None or obj is None:
                    continue
                if not lo - ELEVATION_SLACK_M <= z <= hi + ELEVATION_SLACK_M:
                    outside.append(Ref(page=pt.page, quote=_quote(pt.text, m.group()), object=obj, value=z, unit="m"))
    if not outside:
        return []
    return [_finding(DiscrepancyType.VALUE_CROSS_SECTION_MISMATCH, "absolute_elevation_m", "site", outside + relief,
                     confidence="needs_expert",
                     note=f"elevation 0.000 outside the relief {lo:g}–{hi:g} m (± {ELEVATION_SLACK_M:g})")]
```

- [ ] **Step 4: Run** `uv run pytest tests/test_rules_v1.py -q` — Expected: 4 passed. If the KZ test fails on object resolution (heading «5.1 Қазандық ғимараты»), check `OBJECT_NOUN_RE` (it has «ғимарат») and the single-building fallback.

- [ ] **Step 5: Commit** — «Детектор v1: абсолютная отметка 0.000 вне рельефа площадки».

---

### Task 5: Детектор «метод расчёта объёма»

**Files:**
- Modify: `src/crossvalidation/rules_v1.py`, `tests/test_rules_v1.py`

**Interfaces:**
- Consumes: `rules.Mention` list (`RuleReport.mentions`), parameters `clear_height`, `floor_height` (Task 2).
- Produces: `VOLUME_METHOD_TOL = 0.005`, `MIN_STOREY_M = 2.8`; `check_volume_method(pts, index, mentions: list[Mention], floors: dict[str, int]) -> list[Finding]` — field `construction_volume_m3`, object = building, `needs_expert`.

- [ ] **Step 1: Failing tests** (append):

```python
from src.crossvalidation.rules import Mention
from src.crossvalidation.rules_v1 import check_volume_method


def _m(obj, fld, value, page=1, quote="q"):
    return Mention(obj, fld, value, page, quote, "table", "test")


def test_volume_is_area_times_clear_height():
    pages = _pages(["5.2 Здание цеха", "Высота помещений в чистоте от пола до низа потолка 2,6м"])
    index, pts = _ctx(pages)
    ceh = index.objects[0].id
    mentions = [_m(ceh, "construction_volume_m3", 518.7), _m(ceh, "building_area_m2", 199.5)]
    found = check_volume_method(pts, index, mentions, {})
    assert len(found) == 1 and found[0].object == ceh and found[0].type.value == "TEP_CALCULATION_METHOD"


def test_outer_volume_is_fine():
    pages = _pages(["5.2 Здание цеха", "Высота этажа — 3,3 м, высота помещений в чистоте от пола до низа потолка 2,9 м."])
    index, pts = _ctx(pages)
    ceh = index.objects[0].id
    mentions = [_m(ceh, "construction_volume_m3", 760.0), _m(ceh, "building_area_m2", 199.5)]
    assert check_volume_method(pts, index, mentions, {ceh: 1}) == []


def test_low_average_storey_height():
    pages = _pages(["5.2 Здание цеха", "Описание."])
    index, pts = _ctx(pages)
    ceh = index.objects[0].id
    mentions = [_m(ceh, "construction_volume_m3", 1000.0), _m(ceh, "building_area_m2", 200.0)]
    assert len(check_volume_method(pts, index, mentions, {ceh: 2})) == 1  # 1000 / (200 x 2) = 2,5 m
```

- [ ] **Step 2: Run** — Expected: FAIL, `ImportError: cannot import name 'check_volume_method'`.

- [ ] **Step 3: Implement** (append to `rules_v1.py`; import `Mention` from `rules` and `load_parameters` from `ner.common.parameters`):

```python
VOLUME_METHOD_TOL = 0.005  # V vs S x clear height
MIN_STOREY_M = 2.8  # average storey height by volume below this is implausible; tuned on v4 dev


def _heights(pts: list[PageText], index: ObjectIndex, name: str) -> dict[str, list[Ref]]:
    """object -> heights in metres stated next to a parameter mention ("в чистоте … 2,6м", "таза биіктігі 3,0 м")."""
    param = load_parameters()[name]
    num_m = re.compile(rf"(?P<num>{NUMBER_RE.pattern})\s*м(?![^\W\d_])", re.IGNORECASE)
    out: dict[str, list[Ref]] = {}
    for pt in pts:
        for m in param.mention_re.finditer(pt.text):
            tail = pt.text[m.end(): m.end() + 80]
            h = num_m.search(tail.split(".")[0] + "." if ". " in tail else tail)
            obj = _object(pt, index, m.start(), m.end())
            if h is None or obj is None or (value := _num(h.group("num"))) is None or not 1.5 <= value <= 20:
                continue
            quote = _quote(pt.text, pt.text[m.start(): m.end() + h.end()])
            out.setdefault(obj, []).append(Ref(page=pt.page, quote=quote, object=obj, value=value, unit="m"))
    return out


def check_volume_method(pts: list[PageText], index: ObjectIndex, mentions: list[Mention],
                        floors: dict[str, int]) -> list[Finding]:
    by_obj: dict[str, dict[str, list[Mention]]] = {}
    for m in mentions:
        if m.object and m.field in ("construction_volume_m3", "building_area_m2"):
            by_obj.setdefault(m.object, {}).setdefault(m.field, []).append(m)
    clear = _heights(pts, index, "clear_height")
    out = []
    for obj, fields in by_obj.items():
        volumes, areas = fields.get("construction_volume_m3", []), fields.get("building_area_m2", [])
        hit = None
        for v in volumes:
            for s in areas:
                for h in clear.get(obj, []):
                    if abs(s.value * h.value - v.value) <= VOLUME_METHOD_TOL * v.value:
                        hit = [Ref(page=v.page, quote=v.quote, object=obj, value=v.value, unit="m3",
                                   derived=f"{v.value:g} = {s.value:g} x {h.value:g}"),
                               Ref(page=s.page, quote=s.quote, object=obj, value=s.value, unit="m2"), h]
                        break
                if hit:
                    break
            if hit:
                break
        if hit is None and floors.get(obj) and volumes and areas:
            v, s = min(volumes, key=lambda m: m.value), max(areas, key=lambda m: m.value)
            if v.value / (s.value * floors[obj]) < MIN_STOREY_M:
                hit = [Ref(page=v.page, quote=v.quote, object=obj, value=v.value, unit="m3",
                           derived=f"{v.value:g} / ({s.value:g} x {floors[obj]}) < {MIN_STOREY_M:g} m"),
                       Ref(page=s.page, quote=s.quote, object=obj, value=s.value, unit="m2")]
        if hit:
            out.append(_finding(DiscrepancyType.TEP_CALCULATION_METHOD, "construction_volume_m3", obj, hit,
                                confidence="needs_expert", note=hit[0].derived or ""))
    return out
```

(The `_heights` sentence cut: keep it simple — search the 80 characters after the mention for the first «number м»; the `split(".")` guard is optional; simplify if a test shows it cuts «2,6м». Decimal commas never form «. ».)

- [ ] **Step 4: Run** `uv run pytest tests/test_rules_v1.py -q` — Expected: 7 passed.

- [ ] **Step 5: Commit** — «Детектор v1: метод расчёта строительного объёма».

---

### Task 6: Детектор «подпись таблицы»

**Files:** Modify `src/crossvalidation/rules_v1.py`, `tests/test_rules_v1.py`

**Interfaces:**
- Produces: `check_table_labels(pages, pts, index) -> list[Finding]` — field `object_label`, object = the section's building, `certain`, one ref (the row with the wrong name).

- [ ] **Step 1: Failing tests** (append):

```python
from src.crossvalidation.rules_v1 import check_table_labels

HEADER = ["Наименование", "Площадь застройки", "Строительный объём"]


def _table(rows, top=900.0):
    return PageTable(rows, (0, top, 500, top + 80), rows[0])


def _section_page(heading, rows):
    lines = [heading, "Объёмно-планировочные показатели"] + [" ".join(r) for r in rows]
    page = _page(1, lines, [_table(rows, top=40.0)])
    return [_page(1, ["5. Решения", "5.1 Здание офиса", "Текст."]), page]


def test_wrong_building_in_table():
    pages = _section_page("5.2 Здание цеха", [HEADER, ["Здание офиса", "199,50", "518,70"]])
    pages[1] = Page(2, pages[1].text, pages[1].lines, pages[1].tables)
    index, pts = _ctx(pages)
    found = check_table_labels(pages, pts, index)
    assert len(found) == 1 and found[0].field == "object_label"
    assert index.by_id()[found[0].object].name == "Здание цеха"


def test_own_building_in_table_is_fine():
    pages = _section_page("5.2 Здание цеха", [HEADER, ["Здание цеха", "199,50", "518,70"]])
    pages[1] = Page(2, pages[1].text, pages[1].lines, pages[1].tables)
    index, pts = _ctx(pages)
    assert check_table_labels(pages, pts, index) == []


def test_summary_table_is_not_a_label():
    rows = [HEADER, ["Здание офиса", "312,91", "3116,37"], ["Здание цеха", "199,50", "518,70"]]
    pages = _section_page("5.2 Здание цеха", rows)
    pages[1] = Page(2, pages[1].text, pages[1].lines, pages[1].tables)
    index, pts = _ctx(pages)
    assert check_table_labels(pages, pts, index) == []
```

(The table bbox top 40 puts it below the heading line at top 0; adjust `_section_page` so that `pt.context_above(table.top, carried)` yields the «Здание цеха» object — the heading line must be above the table.)

- [ ] **Step 2: Run** — Expected: FAIL, `ImportError: cannot import name 'check_table_labels'`.

- [ ] **Step 3: Implement** (append; import `OBJECT_NOUN_RE` from `crossvalidation.objects`, `Page` from `ingestion.real`):

```python
def check_table_labels(pages: list[Page], pts: list[PageText], index: ObjectIndex) -> list[Finding]:
    """A one-row table inside the section of building X whose row names another building (or an unknown one)."""
    out = []
    carried = [None] + [pt.ctx_after for pt in pts[:-1]]
    names = index.by_id()
    for page, pt, car in zip(pages, pts, carried, strict=True):
        for table in page.tables:
            section = pt.context_above(table.top, car)
            if section is None:
                continue
            rows = [r for r in table.rows[1:] if any(_num(c) is not None for c in r if c)]
            labels = [next((c for c in r if c and re.search(r"[^\W\d_]", c)), "") for r in rows]
            if len(rows) != 1 or not labels[0]:
                continue  # summary tables (several objects) and unlabelled rows are not checked
            named = index.mentioned(labels[0])
            if section in named or not (named or OBJECT_NOUN_RE.search(labels[0])):
                continue
            quote = _quote(pt.text, " ".join(c for c in rows[0] if c), labels[0])
            out.append(_finding(DiscrepancyType.COPY_PASTE_LABEL, "object_label", section,
                                [Ref(page=pt.page, quote=quote, object=section, value=labels[0])],
                                note=f"table in the section of {names[section].name!r} is labelled {labels[0]!r}"))
    return out
```

- [ ] **Step 4: Run** — Expected: 10 passed.

- [ ] **Step 5: Commit** — «Детектор v1: таблица здания подписана другим зданием».

---

### Task 7: Детектор «параметры здания»

**Files:** Modify `src/crossvalidation/rules_v1.py`, `tests/test_rules_v1.py`

**Interfaces:**
- Consumes: `load_parameters()`, `width_mm` (Task 2).
- Produces: `check_parameters(pts, index) -> list[Finding]` — for each parameter with materials (`blind_area`, `roof`): per building, its values together with the general (`all`) values; a finding when materials differ or widths differ by > 1 %. Object `all` when a general statement takes part, else the building. Value strings `"<material>"` / `"<material>, <width> мм"`.

- [ ] **Step 1: Failing tests** (append):

```python
from src.crossvalidation.rules_v1 import check_parameters


def test_blind_area_material_and_width_differ():
    pages = _pages(["5. Решения", "5.2 Здание цеха", "Отмостка - бетонная кл. В 7.5, шириной 1000 мм"],
                   ["7. Благоустройство", "Вокруг зданий выполняется асфальтобетонная отмостка шириной 1,5м."])
    index, pts = _ctx(pages)
    found = check_parameters(pts, index)
    assert [(f.field, f.object) for f in found] == [("blind_area", "all")]


def test_blind_area_width_after_class_abbreviation():
    pages = _pages(["5.2 Здание цеха", "Отмостка - бетонная кл. В 7.5, шириной 1000 мм. Кровля — плоская."],
                   ["7. Благоустройство", "Вокруг зданий выполняется бетонная отмостка шириной 1,0 м."])
    index, pts = _ctx(pages)
    assert check_parameters(pts, index) == []  # 1000 mm = 1,0 m


def test_roof_differs_in_kazakh():
    pages = _pages(["5.1 Қазандық ғимараты", "Шатыр — ПВХ-мембранадан жасалған жалпақ."],
                   ["7. Абаттандыру", "Ғимараттардың шатыры — профильденген табақтан жасалған еңісті."])
    index, pts = _ctx(pages)
    assert [(f.field, f.object) for f in check_parameters(pts, index)] == [("roof", "all")]
```

- [ ] **Step 2: Run** — Expected: FAIL, ImportError.

- [ ] **Step 3: Implement** (append):

```python
# a phrase ends at a full stop followed by a capitalised word ("кл. В 7.5" does not end it: "В" is followed by a space)
_PHRASE_END = re.compile(r"\.\s+(?=[A-ZА-ЯЁӘҒҚҢӨҰҮҺІ][a-zа-яёәғқңөұүһі])|;")
WIDTH_TOL = 0.01


def _phrase(text: str, start: int, end: int) -> tuple[int, int]:
    s = 0
    for m in _PHRASE_END.finditer(text, 0, start):
        s = m.end()
    e = _PHRASE_END.search(text, end)
    return s, e.start() if e else len(text)


def check_parameters(pts: list[PageText], index: ObjectIndex) -> list[Finding]:
    out = []
    for name, param in load_parameters().items():
        if not param.materials:
            continue
        by_obj: dict[str, list[tuple[Ref, str | None, float | None]]] = {}
        for pt in pts:
            for m in param.mention_re.finditer(pt.text):
                s, e = _phrase(pt.text, m.start(), m.end())
                phrase = pt.text[s:e]
                material = param.material_in(phrase)
                width = width_mm(phrase) if param.has_width else None
                if material is None and width is None:
                    continue
                obj = resolve(pt, index, m.start(), m.end())[0] or "all"
                value = ", ".join(x for x in (material, f"{width:g} мм" if width else None) if x)
                ref = Ref(page=pt.page, quote=_quote(pt.text, phrase.strip()), object=obj, value=value)
                by_obj.setdefault(obj, []).append((ref, material, width))
        general = by_obj.get("all", [])
        for obj, items in by_obj.items():
            group = items + ([] if obj == "all" else general)
            materials = {mat for _, mat, _ in group if mat}
            widths = sorted(w for _, _, w in group if w)
            differs = len(materials) > 1 or (widths and widths[-1] - widths[0] > WIDTH_TOL * widths[-1])
            if obj == "all" and by_obj.keys() - {"all"}:
                continue  # general statements are compared through each building
            if differs:
                scope = "all" if any(r.object == "all" for r, _, _ in group) else obj
                out.append(_finding(DiscrepancyType.PARAMETER_CONTRADICTION, name, scope, [r for r, _, _ in group],
                                    note=f"{name}: " + "; ".join(str(r.value) for r, _, _ in group)))
    return out
```

- [ ] **Step 4: Run** — Expected: 13 passed. If the RU blind-area test yields two findings (one per building plus `all`), deduplicate per (field, scope) by keeping the first.

- [ ] **Step 5: Commit** — «Детектор v1: противоречия в параметрах здания (отмостка, кровля) по словарю».

---

### Task 8: Запуск v1 в конвейере, сообщения в отчёте, изоляция ошибок

**Files:**
- Modify: `src/crossvalidation/rules_v1.py` (`run_rules_v1`), `src/pipeline.py`, `src/crossvalidation/report.py`, `src/crossvalidation/engine.py` (`FIELD_LABELS_RU`), `scripts/evaluate_real.py`
- Test: `tests/test_rules_v1.py`, `tests/test_pipeline.py`

**Interfaces:**
- Produces: `run_rules_v1(pages, report: RuleReport) -> tuple[list[Finding], list[str]]` (findings numbered after v0 ids; warnings for failed detectors); `DETECTORS: list[tuple[str, Callable]]`; `evaluate_real.py --detectors v0|v1`.

- [ ] **Step 1: Failing tests** (append to `tests/test_rules_v1.py`):

```python
from src.crossvalidation import rules_v1
from src.crossvalidation.rules import run_rules


def test_failing_detector_becomes_warning(monkeypatch):
    pages = _pages(["5.1 Здание офиса", "Отмостка — бетонная шириной 1000 мм."])

    def boom(*_):
        raise RuntimeError("boom")

    monkeypatch.setattr(rules_v1, "DETECTORS", [("elevation", boom)] + rules_v1.DETECTORS[1:])
    findings, warnings = rules_v1.run_rules_v1(pages, run_rules(pages))
    assert len(warnings) == 1 and "elevation" in warnings[0]


def test_ids_continue_after_v0():
    pages = _pages(["Абсолютные отметки поверхности изменяются от 314,75 м до 315,04 м."],
                   ["5.1 Здание офиса", "Относительная отметка 0,000 соответствует абсолютной отметке 489,79 м."])
    v0 = run_rules(pages)
    findings, _ = rules_v1.run_rules_v1(pages, v0)
    assert [f.id for f in findings] == [f"P{len(v0.findings) + i}" for i in range(1, len(findings) + 1)]
```

and to `tests/test_pipeline.py` a test that `analyze_package` on a `v4` set with `inject_v4=set(SYNTHETIC_TYPES_V4_EXTRA)` returns findings of the new types with a Russian `message` and does not raise; and that `detectors="v0"` on the same set returns none of them:

```python
def test_v4_findings_reach_the_report(tmp_path):
    from src.ner.common.taxonomy import SYNTHETIC_TYPES_V4_EXTRA

    d = generate_set("ru", 21, tmp_path, scans=False, profile="v4", inject_v4=set(SYNTHETIC_TYPES_V4_EXTRA))
    paths = sorted((d / "text").glob("*.pdf"))
    new = {"TEP_CALCULATION_METHOD", "VALUE_CROSS_SECTION_MISMATCH", "COPY_PASTE_LABEL"}
    v1 = analyze_package(paths)
    got = [f for f in v1["findings"] if f["type"] in new or f["field"] in ("blind_area", "roof")]
    assert got and all(f["message"] for f in got)
    v0 = analyze_package(paths, detectors="v0")
    assert not [f for f in v0["findings"] if f["type"] in new or f["field"] in ("blind_area", "roof")]
```

(`generate_set`/`analyze_package` imports exist at the top of `tests/test_pipeline.py`; check the finding dict keys there — `message` is the field name used by `asdict(Finding)` in `engine.Finding`.)

- [ ] **Step 2: Run** — Expected: FAIL (`run_rules_v1` missing).

- [ ] **Step 3: Implement**

`rules_v1.py` (append; import `Page`, `RuleReport`, `object_index`, `page_texts`, `extract` from `tep_baseline`):

```python
def _floors(pages: list[Page]) -> dict[str, int]:
    ex = extract(pages)
    return {obj: int(c.value) for (obj, fld), c in ex.slots.items() if fld == "floors"}


DETECTORS = [
    ("elevation", lambda pages, pts, index, report: check_elevation(pts, index)),
    ("volume_method", lambda pages, pts, index, report: check_volume_method(pts, index, report.mentions,
                                                                             _floors(pages))),
    ("table_labels", lambda pages, pts, index, report: check_table_labels(pages, pts, index)),
    ("parameters", lambda pages, pts, index, report: check_parameters(pts, index)),
]


def run_rules_v1(pages: list[Page], report: RuleReport) -> tuple[list[Finding], list[str]]:
    index = object_index(pages)
    pts = page_texts(pages, index)
    findings, warnings = [], []
    for name, detect in DETECTORS:
        try:
            findings += detect(pages, pts, index, report)
        except Exception as e:  # one broken check must not cost the whole report
            warnings.append(f"Проверка «{name}» не выполнена: {type(e).__name__}.")
    for i, f in enumerate(findings, start=len(report.findings) + 1):
        f.id = f"P{i}"
    return findings, warnings
```

(`object_index` ids must equal those of `run_rules` — both call `object_index(pages)` with defaults.)

`pipeline.analyze_document`, ПЗ branch, after `v0 = run_rules(pages)`:

```python
        findings = list(v0.findings)
        if detectors == "v1":
            extra, warns = run_rules_v1(pages, v0)
            findings += extra
            doc["_warnings"] = ex.warnings + warns
        doc["_findings"] = pz_findings(findings, names, path, loc)
```

`engine.FIELD_LABELS_RU`: add `"absolute_elevation_m": "Абсолютная отметка 0,000"`, `"object_label": "Подпись таблицы"`, `"blind_area": "Отмостка"`, `"roof": "Кровля"`.

`report.pz_findings`: new branches before the final `else`:

```python
        elif f.type == DiscrepancyType.VALUE_CROSS_SECTION_MISMATCH and f.field == "absolute_elevation_m":
            relief = [r for r in f.refs if isinstance(r.value, list)]
            zs = [r for r in f.refs if not isinstance(r.value, list)]
            lo, hi = relief[0].value
            refs = [_ref(path, loc, r.page, r.quote, r.value, f"Отметка, стр. {r.page}", f.field, r.object) for r in zs] + \
                   [_ref(path, loc, r.page, r.quote, None, f"Рельеф, стр. {r.page}", f.field, "site") for r in relief]
            names_z = ", ".join(f"{_obj_name(r.object, objects)} {fmt(r.value)} м" for r in zs)
            msg = f"Абсолютная отметка 0,000 ({names_z}) вне отметок рельефа площадки {fmt(lo)}–{fmt(hi)} м."
            delta = None
        elif f.type == DiscrepancyType.TEP_CALCULATION_METHOD:
            refs = [_ref(path, loc, r.page, r.quote, r.value, f"стр. {r.page}", f.field, r.object, derived=r.derived)
                    for r in f.refs]
            msg = (f"Строительный объём{where} {fmt(f.refs[0].value)} м³ похож на расчёт не по наружному обмеру: "
                   f"{(f.refs[0].derived or '').replace('x', '×')}.")
            delta = None
        elif f.type == DiscrepancyType.COPY_PASTE_LABEL:
            r = f.refs[0]
            refs = [_ref(path, loc, r.page, r.quote, r.value, f"стр. {r.page}", f.field, r.object)]
            msg = f"Таблица в разделе «{name}» подписана «{r.value}»."
            delta = None
```

and in the `PARAMETER_CONTRADICTION` branch add, before `fire_resistance`:

```python
            if f.field in ("blind_area", "roof"):
                values = "; ".join(f"{_obj_name(r.object, objects)}: {r.value}" for r in f.refs)
                msg = f"{label(f.field)}{where}: в документе описана по-разному — {values}."
            elif f.field == "fire_resistance":
```

(Map material ids to Russian words for the message: `{"concrete": "бетонная", "asphalt": "асфальтобетонная", "membrane": "мембрана", "bitumen": "рулонная", "profiled": "профлист"}` applied to the value string.)

`scripts/evaluate_real.py`: `--detectors` argument (default `v1`); after `report = run_rules(...)`: `if args.detectors == "v1": extra, _ = run_rules_v1(pages, report); report.findings += extra`.

- [ ] **Step 4: Run** `uv run pytest -q -p no:warnings` — Expected: all pass. Run `uv run python scripts/evaluate_real.py` and record found/missed/false (expected: R3, R6, R8, R9 now found; R1, R2, R4, R5 still found; false 0 — if not, note which and why in the ledger; tune only generic patterns, never document-specific strings).

- [ ] **Step 5: Commit** — «Детекторы v1 в конвейере и отчёте; S2 = v1; проверка на реальной ОПЗ».

---

### Task 9: Оценка на `v4`, пороги на dev, итог на test, README

**Files:**
- Create: `scripts/eval_detectors.py`
- Modify: `src/crossvalidation/rules_v1.py` (constants only), `README.md`, spec §8 if a criterion needs a recorded note

**Interfaces:**
- Produces: CLI `uv run python scripts/eval_detectors.py --profile v4 --seeds 1-50 [--lang ru kz] [--json PATH]`.

- [ ] **Step 1: Script** `scripts/eval_detectors.py`:

```python
"""S1 vs S2 on synthetic sets: P/R/F1 by discrepancy type (slots = type + field, as in E3).

    uv run python scripts/eval_detectors.py --profile v4 --seeds 1-50          # development
    uv run python scripts/eval_detectors.py --profile v4 --seeds 9000-9099     # final, once
    uv run python scripts/eval_detectors.py --profile v2 --seeds 8000-8019     # regression: no new false alarms
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.bench import gt_slots  # noqa: E402
from src.evaluation.systems import RulesSystem, RulesSystemV1  # noqa: E402
from src.synthesis.generator import PROFILES, generate_set  # noqa: E402


def seeds(spec: str) -> list[int]:
    lo, _, hi = spec.partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


def prf(tp: int, fp: int, fn: int) -> str:
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else float("nan")
    return f"{p:5.2f} {r:5.2f} {f:5.2f}  (tp {tp} fp {fp} fn {fn})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile", default="v4", choices=PROFILES)
    ap.add_argument("--seeds", default="1-50")
    ap.add_argument("--lang", nargs="+", default=["ru", "kz"])
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    systems = [RulesSystem(), RulesSystemV1()]
    report = {}
    with tempfile.TemporaryDirectory() as tmp:
        for lang in args.lang:
            counts = {s.name: (Counter(), Counter(), Counter()) for s in systems}
            for seed in seeds(args.seeds):
                d = generate_set(lang, seed, Path(tmp), scans=False, profile=args.profile)
                want = gt_slots(json.loads((d / "ground_truth.json").read_text(encoding="utf-8")))
                paths = sorted((d / "text").glob("*.pdf"))
                for s in systems:
                    got = s.detect(paths, lang)
                    tp, fp, fn = counts[s.name]
                    for k in want & got:
                        tp[k] += 1
                    for k in got - want:
                        fp[k] += 1
                    for k in want - got:
                        fn[k] += 1
            print(f"\n== {args.profile} {lang}, seeds {args.seeds}")
            keys = sorted({k for c in counts.values() for part in c for k in part})
            for s in systems:
                tp, fp, fn = counts[s.name]
                print(f"{s.name} ALL {'':<40} {prf(sum(tp.values()), sum(fp.values()), sum(fn.values()))}")
                for k in keys:
                    print(f"   {k[0]:<28} {k[1]:<22} {prf(tp[k], fp[k], fn[k])}")
                report[f"{lang}_{s.name}"] = {"|".join(k): [tp[k], fp[k], fn[k]] for k in keys}
    if args.json:
        args.json.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Dev run and tuning**

Run: `uv run python scripts/eval_detectors.py --profile v4 --seeds 1-50 --json build/research/detectors_v4_dev.json`
Run: `uv run python scripts/eval_detectors.py --profile v2 --seeds 8000-8019`

Read false positives / negatives per new slot. Tune only `ELEVATION_SLACK_M`, `VOLUME_METHOD_TOL`, `MIN_STOREY_M`, `WIDTH_TOL` and generic patterns (no seed-specific strings); every change goes in the ledger. Guards after tuning: `uv run pytest -q`, `scripts/evaluate_real.py` (R1–R6, R8, R9 found, 0 false), v2 regression (S2 has no more false positives than S1).

- [ ] **Step 3: Commit thresholds** — «Пороги детекторов v1 подобраны на v4 dev».

- [ ] **Step 4: Final test run, once**

Run: `uv run python scripts/eval_detectors.py --profile v4 --seeds 9000-9099 --json build/research/detectors_v4_test.json`

No constant changes after this run.

- [ ] **Step 5: README**

New subsection after «Незнакомые формулировки ТЭП» — «Детекторы несоответствий v1»: what the four detectors check (one line each), the `parameter_lexicon.json` mechanism, S1 vs S2 table by new type on `v4` test (P / R / F1 for RU and KZ), the v2 regression line, the real ОПЗ line («R3, R6, R8, R9 найдены; правила писались с оглядкой на этот документ — это проверка работоспособности, а не метрика»), and that S1 stays pinned to `protocol-v1`. Update the «Структура» block (`rules_v1.py`, `parameters.py`, `parameter_lexicon.json`, `values_v4.py`, `pz_v4.py`, `eval_detectors.py`, `snapshot_s1.py`). If a type misses the 0,8 bar, say which and why next to the table.

- [ ] **Step 6: Final check and commit**

Run: `uv run pytest -q -p no:warnings && uv run ruff check src scripts tests` — all green.
Commit — «README: детекторы несоответствий v1, итог на v4».
