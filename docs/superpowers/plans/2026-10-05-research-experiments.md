# Research Experiments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the evaluation harness and run experiments E1–E4 from the research spec, so the thesis has measured results for RQ1–RQ3.

**Architecture:** One shared scoring module (`src/evaluation/bench.py`) turns any system's output into `(type, field)` slots and scores them against ground truth per language, level and type, with bootstrap intervals over sets. Systems (rules S1, LLM L1, hybrid H1) sit behind one `System` interface in `src/evaluation/systems.py`; the LLM client is injectable so tests never call the network. Experiment scripts in `scripts/` only wire datasets, systems and output files together and write to `build/research/` (git-ignored).

**Tech Stack:** Python 3.12, pytest, pydantic (existing), `anthropic` SDK (new dependency, L1 only), existing pipeline `src.pipeline.analyze_package`, `src.crossvalidation.rules.run_rules`, `src.evaluation.{match,extractability,annotations,schema}`.

**Spec:** `docs/superpowers/specs/2026-10-05-research-design.md`

## Global Constraints

- Real documents never leave the machine: no real document text goes to any external service (spec §4). L1/H1 on real documents run only with the explicit flag `--allow-real-llm`, and the LLM cache is never written for real documents.
- Commercial tools (Armeta, Norma.AI) receive synthetic sets only, and their results are reported as observations, not F1 (spec §4, E4).
- Evaluation seeds are frozen before any experiment: `FINAL_SEEDS = 8000–8099` (E2, E3), `E4_SEEDS = 9000–9019`; neither range may be used for rule development (spec §5). Development ranges 3000–3049 and 6000–6049 and held-out 7000–7099 are already seen.
- The matching rule `src/evaluation/match.py` and the metric definitions are not changed after the protocol is frozen (Task 1) (spec §6).
- L1 model id, prompt version and run count are recorded in every result file (spec §4, §8).
- `build/` and `data/real/` stay git-ignored; result files that quote real documents are never committed.
- Code style: ruff, line length 120, `from __future__ import annotations`, docstring at the top of each module (matches existing files).

## Review Focus

1. LLM returns prose around the JSON, invalid JSON, or an unknown type id → must not crash; unknown types are dropped and counted (Task 4).
2. A set with zero ground-truth discrepancies (negative sample) → false positives still counted, recall is `None`, not 0 or a crash (Task 2).
3. The same slot predicted twice by a system → counted once (Task 2 uses sets; Task 3 test pins it).
4. A PDF without text layer (scan) → L1 skips the call and returns no detections instead of sending an empty prompt (Task 4).
5. Real document with L1 requested but no `--allow-real-llm` → refuses with a clear error; cache never written in real mode (Task 7).

---

### Task 1: Freeze the protocol

**Files:**
- Create: `src/evaluation/protocol.py`
- Create: `docs/research/protocol.md`
- Test: `tests/test_protocol.py`

**Interfaces:**
- Produces: `PROTOCOL_VERSION: str`, `FINAL_SEEDS: tuple[int, int]`, `E4_SEEDS: tuple[int, int]`, `SEEN_SEEDS: tuple[tuple[int, int], ...]`, `LLM_MODEL: str`, `PROMPT_VERSION: str`, `LLM_RUNS: int`, `seed_list(span: tuple[int, int]) -> list[int]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_protocol.py
from src.evaluation import protocol


def test_final_and_e4_seeds_do_not_overlap_seen_ranges():
    final = set(protocol.seed_list(protocol.FINAL_SEEDS)) | set(protocol.seed_list(protocol.E4_SEEDS))
    for span in protocol.SEEN_SEEDS:
        assert final.isdisjoint(protocol.seed_list(span))


def test_final_and_e4_are_disjoint_and_sized():
    final = protocol.seed_list(protocol.FINAL_SEEDS)
    e4 = protocol.seed_list(protocol.E4_SEEDS)
    assert len(final) == 100 and len(e4) == 20
    assert set(final).isdisjoint(e4)


def test_llm_settings_are_pinned():
    assert protocol.LLM_MODEL and protocol.PROMPT_VERSION and protocol.LLM_RUNS >= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_protocol.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.evaluation.protocol'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evaluation/protocol.py
"""Frozen evaluation protocol of the research experiments (spec 2026-10-05-research-design.md).

Changing anything here after the first run of E2/E3 invalidates the comparison: bump ``PROTOCOL_VERSION``
and rerun every experiment.
"""

from __future__ import annotations

PROTOCOL_VERSION = "1"

# Seeds the rules were developed on or already evaluated on (README): never use them for final numbers.
SEEN_SEEDS: tuple[tuple[int, int], ...] = ((1, 200), (2000, 2009), (3000, 3049), (5001, 5040), (6000, 6049),
                                           (7000, 7099))
FINAL_SEEDS = (8000, 8099)  # E2 and E3, 100 sets per language
E4_SEEDS = (9000, 9019)  # E4, 20 sets per language, given to commercial tools

LLM_MODEL = "claude-sonnet-5-5"
PROMPT_VERSION = "p1"
LLM_RUNS = 3


def seed_list(span: tuple[int, int]) -> list[int]:
    return list(range(span[0], span[1] + 1))
```

```markdown
<!-- docs/research/protocol.md -->
# Протокол оценки (версия 1)

Заморожен перед запуском E2/E3. Источник правды — `src/evaluation/protocol.py`.

- **Единица сопоставления:** слот `(type, field)` из `ground_truth.json`; для `AREA_PZ_VS_AR_EXPLICATION` и
  `COST_OBJECT_ESTIMATE_VS_SUMMARY` поле пустое. Второй, более грубый уровень — только `type`.
- **Метрики:** precision, recall, F1 по языку, уровню таксономии и типу; ложные срабатывания на набор;
  95 % интервал F1 бутстрепом по наборам (1000 повторов, seed 0).
- **Данные:** синтетика профиля v2, seeds 8000–8099 (E2, E3), 9000–9019 (E4). Не использовались при разработке.
- **LLM (L1):** модель и версия промпта из `protocol.py`, 3 запуска, ответы кэшируются на диск.
- **Реальные документы:** сопоставление `src/evaluation/match.py`; не изменять после заморозки.
- **Запреты:** реальные документы не уходят во внешние сервисы; коммерческие продукты получают только синтетику.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_protocol.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/protocol.py docs/research/protocol.md tests/test_protocol.py
git commit -m "Протокол оценки: зафиксированы seeds, метрики и параметры LLM"
```

---

### Task 2: Scoring module

**Files:**
- Create: `src/evaluation/bench.py`
- Test: `tests/test_bench.py`

**Interfaces:**
- Consumes: `TYPE_LEVEL`, `DiscrepancyType` from `src/ner/common/taxonomy.py`
- Produces:
  - `Slot = tuple[str, str]`
  - `slot(dtype: str, fld: str) -> Slot`
  - `gt_slots(gt: dict) -> set[Slot]`
  - `SetRecord(lang: str, set_id: str, tp: Counter, fp: Counter, fn: Counter)`
  - `score_set(lang: str, set_id: str, want: set[Slot], got: set[Slot], granularity: str = "slot") -> SetRecord`
  - `Scoreboard.add(rec)`, `.prf(lang=None, level=None) -> tuple[float | None, float | None, float | None]`, `.fp_per_set(lang=None) -> float | None`, `.bootstrap_f1(lang=None, level=None, iters=1000, seed=0) -> tuple[float, float] | None`, `.by_type(lang=None) -> dict[str, tuple[int, int, int]]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bench.py
from src.evaluation.bench import Scoreboard, gt_slots, score_set, slot

AREA = "AREA_PZ_VS_AR_EXPLICATION"
TOTAL = "TABLE_TOTAL_MISMATCH"
STMT = "STATEMENT_CONTRADICTION"


def test_slot_drops_field_for_slot_free_types_and_local_qty_prefix():
    assert slot(AREA, "total_area_m2") == (AREA, "")
    assert slot("MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE", "local_qty.rebar_a500c_t") == (
        "MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE", "rebar_a500c_t")


def test_gt_slots_reads_discrepancies():
    gt = {"discrepancies": [{"type": AREA, "field": "x"}, {"type": TOTAL, "field": "t1"}]}
    assert gt_slots(gt) == {(AREA, ""), (TOTAL, "t1")}


def test_score_set_counts_tp_fp_fn_by_type():
    rec = score_set("ru", "s1", {(AREA, ""), (TOTAL, "t1")}, {(AREA, ""), (TOTAL, "t2")})
    assert (rec.tp[AREA], rec.fp[TOTAL], rec.fn[TOTAL]) == (1, 1, 1)


def test_type_granularity_ignores_field():
    rec = score_set("ru", "s1", {(TOTAL, "t1")}, {(TOTAL, "t2")}, granularity="type")
    assert rec.tp[TOTAL] == 1 and not rec.fp and not rec.fn


def test_negative_set_has_false_positive_and_no_recall():
    board = Scoreboard()
    board.add(score_set("ru", "neg", set(), {(AREA, "")}))
    p, r, f = board.prf()
    assert (p, r, f) == (0.0, None, None)
    assert board.fp_per_set() == 1.0


def test_same_slot_predicted_twice_counts_once():
    got = [(AREA, ""), (AREA, "")]
    rec = score_set("ru", "s", {(AREA, "")}, set(got))
    assert rec.tp[AREA] == 1 and not rec.fp


def test_prf_by_level_and_language():
    board = Scoreboard()
    board.add(score_set("ru", "a", {(AREA, "")}, {(AREA, "")}))  # numeric tp
    board.add(score_set("kz", "b", {(STMT, "f")}, set()))  # logical fn
    assert board.prf(level="numeric")[1] == 1.0
    assert board.prf(level="logical")[1] == 0.0
    assert board.prf(lang="kz", level="numeric") == (None, None, None)


def test_bootstrap_interval_brackets_point_estimate_and_is_reproducible():
    board = Scoreboard()
    for i in range(30):
        got = {(AREA, "")} if i % 3 else set()
        board.add(score_set("ru", f"s{i}", {(AREA, "")}, got))
    lo, hi = board.bootstrap_f1(iters=200, seed=0)
    assert lo <= board.prf()[2] <= hi
    assert (lo, hi) == board.bootstrap_f1(iters=200, seed=0)


def test_bootstrap_returns_none_without_data():
    assert Scoreboard().bootstrap_f1() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bench.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.evaluation.bench'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evaluation/bench.py
"""Scoring of discrepancy detection against synthetic ground truth, shared by every compared system.

A system's output is a set of slots ``(type, field)``; ground truth gives the same from ``ground_truth.json``.
Records are kept per set so intervals can be bootstrapped over sets.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from src.ner.common.taxonomy import TYPE_LEVEL, DiscrepancyType

Slot = tuple[str, str]
SLOT_FREE_TYPES = frozenset({"COST_OBJECT_ESTIMATE_VS_SUMMARY", "AREA_PZ_VS_AR_EXPLICATION"})


def slot(dtype: str, fld: str) -> Slot:
    if dtype in SLOT_FREE_TYPES:
        return dtype, ""
    return dtype, fld.removeprefix("local_qty.")


def gt_slots(gt: dict) -> set[Slot]:
    return {slot(d["type"], d["field"]) for d in gt["discrepancies"]}


@dataclass
class SetRecord:
    lang: str
    set_id: str
    tp: Counter
    fp: Counter
    fn: Counter


def score_set(lang: str, set_id: str, want: set[Slot], got: set[Slot], granularity: str = "slot") -> SetRecord:
    if granularity == "type":
        want, got = {(t, "") for t, _ in want}, {(t, "") for t, _ in got}
    rec = SetRecord(lang, set_id, Counter(), Counter(), Counter())
    for t, _ in want & got:
        rec.tp[t] += 1
    for t, _ in got - want:
        rec.fp[t] += 1
    for t, _ in want - got:
        rec.fn[t] += 1
    return rec


def _level(dtype: str) -> str:
    return TYPE_LEVEL[DiscrepancyType(dtype)].value


def _prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    if p is None or r is None:
        return p, r, None
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


class Scoreboard:
    def __init__(self) -> None:
        self.records: list[SetRecord] = []

    def add(self, rec: SetRecord) -> None:
        self.records.append(rec)

    @staticmethod
    def _counts(recs: list[SetRecord], level: str | None) -> tuple[int, int, int]:
        def total(c: Counter) -> int:
            return sum(n for t, n in c.items() if level is None or _level(t) == level)

        return (sum(total(r.tp) for r in recs), sum(total(r.fp) for r in recs), sum(total(r.fn) for r in recs))

    def _select(self, lang: str | None) -> list[SetRecord]:
        return [r for r in self.records if lang is None or r.lang == lang]

    def prf(self, lang: str | None = None, level: str | None = None):
        return _prf(*self._counts(self._select(lang), level))

    def fp_per_set(self, lang: str | None = None) -> float | None:
        recs = self._select(lang)
        return sum(sum(r.fp.values()) for r in recs) / len(recs) if recs else None

    def by_type(self, lang: str | None = None) -> dict[str, tuple[int, int, int]]:
        recs = self._select(lang)
        types = sorted({t for r in recs for c in (r.tp, r.fp, r.fn) for t in c})
        return {t: (sum(r.tp[t] for r in recs), sum(r.fp[t] for r in recs), sum(r.fn[t] for r in recs))
                for t in types}

    def bootstrap_f1(self, lang: str | None = None, level: str | None = None, iters: int = 1000,
                     seed: int = 0) -> tuple[float, float] | None:
        recs = self._select(lang)
        if not recs:
            return None
        rng = random.Random(seed)
        scores = []
        for _ in range(iters):
            sample = [recs[rng.randrange(len(recs))] for _ in recs]
            f = _prf(*self._counts(sample, level))[2]
            if f is not None:
                scores.append(f)
        if not scores:
            return None
        scores.sort()
        return scores[int(0.025 * (len(scores) - 1))], scores[int(0.975 * (len(scores) - 1))]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_bench.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/bench.py tests/test_bench.py
git commit -m "Общий модуль оценки: слоты, P/R/F1 по языку и уровню, бутстреп по наборам"
```

---

### Task 3: System interface and the rules system S1

**Files:**
- Create: `src/evaluation/systems.py`
- Test: `tests/test_systems.py`

**Interfaces:**
- Consumes: `analyze_package(paths: list[Path]) -> dict` (`src/pipeline.py`), `slot`, `Slot` from `bench.py`
- Produces:
  - `class System(Protocol)`: `name: str`; `detect(paths: list[Path], lang: str) -> set[Slot]`
  - `class RulesSystem` (`name = "S1"`), `RulesSystem().detect(paths, lang)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_systems.py
import json

from src.evaluation.bench import gt_slots
from src.evaluation.systems import RulesSystem
from src.synthesis.generator import generate_set


def test_rules_system_matches_ground_truth_on_v1_set(tmp_path):
    set_dir = generate_set("ru", 31, tmp_path, scans=False, profile="v1")
    gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
    got = RulesSystem().detect(sorted(set_dir.glob("text/*.pdf")), "ru")
    assert got == gt_slots(gt)


def test_rules_system_returns_set_of_slots(tmp_path):
    set_dir = generate_set("kz", 32, tmp_path, scans=False, profile="v1")
    got = RulesSystem().detect(sorted(set_dir.glob("text/*.pdf")), "kz")
    assert isinstance(got, set) and all(isinstance(s, tuple) and len(s) == 2 for s in got)
    assert RulesSystem.name == "S1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_systems.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.evaluation.systems'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evaluation/systems.py
"""Compared systems behind one interface: a package of PDFs in, a set of detected slots out."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.evaluation.bench import Slot, slot
from src.pipeline import analyze_package


class System(Protocol):
    name: str

    def detect(self, paths: list[Path], lang: str) -> set[Slot]: ...


class RulesSystem:
    """S1: the rule-based pipeline (extraction + checks v0 + cross-section engine)."""

    name = "S1"

    def detect(self, paths: list[Path], lang: str) -> set[Slot]:
        report = analyze_package(paths)
        return {slot(f["type"], f["field"]) for f in report["findings"] if f["verdict"] != "MATCH"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_systems.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/systems.py tests/test_systems.py
git commit -m "Интерфейс сравниваемых систем и S1 (правила) поверх analyze_package"
```

---

### Task 4: LLM system L1

> Before writing the client in Step 3, load the `claude-api` skill and check the `messages.create` call and model id against it.

**Files:**
- Modify: `pyproject.toml` (add `anthropic`)
- Create: `src/evaluation/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `slot`, `Slot` (`bench.py`); `LLM_MODEL`, `PROMPT_VERSION` (`protocol.py`); `DiscrepancyType`, `TYPE_LEVEL` (`taxonomy.py`); `FIELD_LABELS_RU` (`src/crossvalidation/engine.py`); `extract_text(path) -> str` (`src/ingestion/common/pdf.py`)
- Produces:
  - `class LLMClient(Protocol)`: `complete(self, system: str, user: str, run: int = 0) -> str`
  - `class AnthropicClient(model=LLM_MODEL, cache_dir: Path | None = None, max_tokens: int = 4096)` implementing `LLMClient`
  - `parse_items(raw: str) -> tuple[list[dict], int]` (valid items with known `type`; count dropped)
  - `class LLMSystem(client: LLMClient, run: int = 0)`: `name = "L1"`, `detect(paths, lang) -> set[Slot]`, `detect_items(paths) -> list[dict]`, attributes `parse_failures: int`, `dropped: int`
  - `build_prompt(docs: dict[str, str]) -> tuple[str, str]` (system, user)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm.py
import json

from src.evaluation.llm import LLMSystem, build_prompt, parse_items
from src.synthesis.generator import generate_set

AREA = "AREA_PZ_VS_AR_EXPLICATION"


class FakeClient:
    def __init__(self, reply: str):
        self.reply, self.calls = reply, []

    def complete(self, system: str, user: str, run: int = 0) -> str:
        self.calls.append((system, user, run))
        return self.reply


def test_parse_items_accepts_fenced_json_with_prose_around():
    raw = 'Вот результат:\n```json\n[{"type": "%s", "field": "total_area_m2"}]\n```\nГотово.' % AREA
    items, dropped = parse_items(raw)
    assert [i["type"] for i in items] == [AREA] and dropped == 0


def test_parse_items_drops_unknown_types_and_counts_them():
    raw = json.dumps([{"type": AREA, "field": "x"}, {"type": "NOT_A_TYPE", "field": "y"}, "junk"])
    items, dropped = parse_items(raw)
    assert len(items) == 1 and dropped == 2


def test_parse_items_survives_garbage():
    assert parse_items("совсем не json") == ([], 1)
    assert parse_items("") == ([], 1)


def test_prompt_lists_all_documents_and_allowed_types():
    system, user = build_prompt({"PZ": "текст ПЗ", "AR": "текст АР"})
    assert "=== PZ ===" in user and "текст АР" in user
    assert AREA in system and "STATEMENT_CONTRADICTION" in system


def test_llm_system_returns_slots_and_counts_duplicates_once(tmp_path):
    set_dir = generate_set("ru", 31, tmp_path, scans=False, profile="v1")
    reply = json.dumps([{"type": AREA, "field": "total_area_m2"}, {"type": AREA, "field": "total_area_m2"}])
    system = LLMSystem(FakeClient(reply))
    assert system.detect(sorted(set_dir.glob("text/*.pdf")), "ru") == {(AREA, "")}


def test_llm_system_tracks_parse_failures(tmp_path):
    set_dir = generate_set("ru", 31, tmp_path, scans=False, profile="v1")
    system = LLMSystem(FakeClient("нет ответа"))
    assert system.detect(sorted(set_dir.glob("text/*.pdf")), "ru") == set()
    assert system.parse_failures == 1


def test_llm_system_skips_call_for_documents_without_text(tmp_path):
    set_dir = generate_set("ru", 31, tmp_path, scans=True, profile="v1")
    client = FakeClient("[]")
    system = LLMSystem(client)
    assert system.detect(sorted(set_dir.glob("scan/*.pdf")), "ru") == set()
    assert client.calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.evaluation.llm'`

- [ ] **Step 3: Write minimal implementation**

Add the dependency first:

```bash
uv add anthropic
```

```python
# src/evaluation/llm.py
"""L1: a zero-shot LLM as a discrepancy detector, behind the same interface as the rule-based system.

The prompt is fixed (``PROMPT_VERSION``) and lists the taxonomy types and TEP field ids so the answer can be
compared slot by slot. The client is injectable; ``AnthropicClient`` caches answers on disk so reruns are
reproducible and free.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Protocol

from src.crossvalidation.engine import FIELD_LABELS_RU
from src.evaluation.bench import Slot, slot
from src.evaluation.protocol import LLM_MODEL, PROMPT_VERSION
from src.ingestion.common.pdf import extract_text
from src.ner.common.taxonomy import TYPE_LEVEL, DiscrepancyType

TYPE_HINTS = {
    "AREA_PZ_VS_AR_EXPLICATION": "общая площадь в ПЗ не равна сумме экспликации помещений в АР",
    "MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE": "объём или масса материала в КР не равны количеству в локальной смете",
    "COST_OBJECT_ESTIMATE_VS_SUMMARY": "итог объектной сметы не равен строке в сводном сметном расчёте",
    "MISSING_MANDATORY_TEP": "обязательный ТЭП отсутствует в разделе, где должен быть",
    "TEP_CROSS_SECTION_MISMATCH": "один ТЭП одного объекта указан по-разному в разных местах",
    "TABLE_TOTAL_MISMATCH": "итог таблицы не равен сумме её строк",
    "VALUE_CROSS_SECTION_MISMATCH": "значение (например, абсолютная отметка) различается между разделами",
    "LOCAL_ESTIMATE_VS_SUMMARY": "итог локальной сметы не равен строке сметного расчёта",
    "PARAMETER_CONTRADICTION": "сейсмичность, огнестойкость или материал названы по-разному",
    "STATEMENT_CONTRADICTION": "в тексте есть противоречащие утверждения",
    "TEP_CALCULATION_METHOD": "значение посчитано неверным методом",
    "GEOMETRY_INCONSISTENCY": "площадь застройки меньше площади в осях и т. п.",
    "COPY_PASTE_LABEL": "неверная подпись объекта или таблицы (следы копирования)",
    "IRRELEVANT_REFERENCE": "нормативная ссылка не относится к объекту",
}
KNOWN_TYPES = {t.value for t in DiscrepancyType}


class LLMClient(Protocol):
    def complete(self, system: str, user: str, run: int = 0) -> str: ...


def build_prompt(docs: dict[str, str]) -> tuple[str, str]:
    types = "\n".join(f"- {t}: {TYPE_HINTS[t]} (уровень {TYPE_LEVEL[DiscrepancyType(t)].value})"
                      for t in TYPE_HINTS)
    fields = ", ".join(sorted(FIELD_LABELS_RU))
    system = (
        "Ты проверяешь комплект проектной документации (разделы ПЗ, АР, КР, смета; русский или казахский язык) "
        "на несоответствия между разделами и внутри них. Найди только те несоответствия, которые подтверждаются "
        "текстом. Допустимые типы:\n" + types + "\n\nПоле field выбирай из: " + fields + ". Если подходящего нет, "
        "оставь пустую строку.\nОтветь только JSON-массивом объектов вида "
        '{"type": "<тип>", "field": "<поле>", "object": "<здание или пусто>", "evidence": "<короткая цитата>"}. '
        "Если несоответствий нет, верни []."
    )
    user = "\n\n".join(f"=== {name} ===\n{text}" for name, text in docs.items())
    return system, user


def parse_items(raw: str) -> tuple[list[dict], int]:
    """Valid items (known ``type``) and the number of dropped or unparseable entries."""
    match = re.search(r"\[.*\]", raw, flags=re.DOTALL)
    if not match:
        return [], 1
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return [], 1
    if not isinstance(data, list):
        return [], 1
    items = [d for d in data if isinstance(d, dict) and d.get("type") in KNOWN_TYPES]
    return items, len(data) - len(items)


class AnthropicClient:
    def __init__(self, model: str = LLM_MODEL, cache_dir: Path | None = None, max_tokens: int = 4096):
        import anthropic

        self._api = anthropic.Anthropic()
        self.model, self.cache_dir, self.max_tokens = model, cache_dir, max_tokens

    def _cache_path(self, system: str, user: str, run: int) -> Path | None:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256(f"{self.model}|{PROMPT_VERSION}|{run}|{system}|{user}".encode()).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def complete(self, system: str, user: str, run: int = 0) -> str:
        path = self._cache_path(system, user, run)
        if path is not None and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["text"]
        reply = self._api.messages.create(model=self.model, max_tokens=self.max_tokens, system=system,
                                          messages=[{"role": "user", "content": user}])
        text = "".join(block.text for block in reply.content if block.type == "text")
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")
        return text


class LLMSystem:
    """L1: send the text layer of every document in one prompt, read the JSON answer as slots."""

    name = "L1"

    def __init__(self, client: LLMClient, run: int = 0):
        self.client, self.run = client, run
        self.parse_failures = 0
        self.dropped = 0

    def detect_items(self, paths: list[Path]) -> list[dict]:
        docs = {p.stem: extract_text(p).replace("\f", "\n") for p in paths if p.suffix.lower() == ".pdf"}
        docs = {name: text for name, text in docs.items() if text.strip()}
        if not docs:
            return []
        system, user = build_prompt(docs)
        items, dropped = parse_items(self.client.complete(system, user, self.run))
        self.dropped += dropped
        self.parse_failures += int(dropped > 0 and not items)
        return items

    def detect(self, paths: list[Path], lang: str) -> set[Slot]:
        return {slot(i["type"], str(i.get("field", ""))) for i in self.detect_items(paths)}
```

> Note: `parse_failures` counts a call whose whole answer was unusable (nothing valid, something dropped). A model that correctly answers `[]` drops nothing and is not a failure; add a test for that case in this step.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_llm.py -v`
Expected: PASS (7 passed, plus the `[]` test you added: `LLMSystem(FakeClient("[]"))` gives `parse_failures == 0`).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/evaluation/llm.py tests/test_llm.py
git commit -m "L1: LLM как детектор несоответствий с фиксированным промптом и кэшем"
```

---

### Task 5: Hybrid system H1

**Files:**
- Modify: `src/evaluation/systems.py`
- Test: `tests/test_hybrid.py`

**Interfaces:**
- Consumes: `LLMSystem.detect_items(paths) -> list[dict]` (Task 4), `RulesSystem` (Task 3), `slot`, `TYPE_LEVEL`, `Level`
- Produces: `HybridSystem(rules: System, llm: LLMSystem, llm_levels: tuple[Level, ...] = (Level.LOGICAL, Level.ARTIFACT))`, `name = "H1"`, `detect(paths, lang) -> set[Slot]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hybrid.py
from pathlib import Path

from src.evaluation.systems import HybridSystem

AREA = "AREA_PZ_VS_AR_EXPLICATION"
STMT = "STATEMENT_CONTRADICTION"
COPY = "COPY_PASTE_LABEL"


class StubRules:
    name = "S1"

    def detect(self, paths, lang):
        return {(AREA, "")}


class StubLLM:
    def __init__(self, items):
        self.items = items

    def detect_items(self, paths):
        return self.items


def test_hybrid_takes_rules_plus_llm_logical_and_artifact_only():
    llm = StubLLM([{"type": STMT, "field": ""}, {"type": COPY, "field": "f"}, {"type": "TABLE_TOTAL_MISMATCH",
                                                                               "field": "t"}])
    got = HybridSystem(StubRules(), llm).detect([Path("x.pdf")], "ru")
    assert got == {(AREA, ""), (STMT, ""), (COPY, "f")}


def test_hybrid_ignores_llm_numeric_claims_even_when_rules_found_nothing():
    class NoRules(StubRules):
        def detect(self, paths, lang):
            return set()

    llm = StubLLM([{"type": AREA, "field": "total_area_m2"}])
    assert HybridSystem(NoRules(), llm).detect([Path("x.pdf")], "ru") == set()


def test_hybrid_name():
    assert HybridSystem(StubRules(), StubLLM([])).name == "H1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_hybrid.py -v`
Expected: FAIL with `ImportError: cannot import name 'HybridSystem'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/evaluation/systems.py` and extend its imports:

```python
# add to imports
from src.ner.common.taxonomy import TYPE_LEVEL, DiscrepancyType, Level


class HybridSystem:
    """H1: rules own the numeric core; the LLM contributes only the levels rules cannot reach."""

    name = "H1"

    def __init__(self, rules: System, llm, llm_levels: tuple[Level, ...] = (Level.LOGICAL, Level.ARTIFACT)):
        self.rules, self.llm, self.llm_levels = rules, llm, llm_levels

    def detect(self, paths: list[Path], lang: str) -> set[Slot]:
        got = set(self.rules.detect(paths, lang))
        for item in self.llm.detect_items(paths):
            if TYPE_LEVEL[DiscrepancyType(item["type"])] in self.llm_levels:
                got.add(slot(item["type"], str(item.get("field", ""))))
        return got
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_hybrid.py tests/test_systems.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/systems.py tests/test_hybrid.py
git commit -m "H1: гибрид правил и LLM (LLM только для уровней logical и artifact)"
```

---

### Task 6: E1 — ceiling by extractability (RQ1)

**Files:**
- Create: `src/evaluation/ceiling.py`
- Create: `scripts/exp_e1_ceiling.py`
- Test: `tests/test_ceiling.py`

**Interfaces:**
- Consumes: `RealAnnotation`, `Finding`, `Ref` (`schema.py`); `locate(pages, obj, fld, value, hint_page) -> ValueHit` (`extractability.py`); `Page` (`src/ingestion/real.py`); `Level`
- Produces:
  - `classify_finding(f: Finding, pages: list[Page]) -> str` returning `"table_reachable"`, `"text_reachable"` or `"beyond_rules"`
  - `ceiling_table(findings_classes: list[tuple[Finding, str]]) -> dict[str, dict[str, int]]` (level → class → count)

Definitions (written into the module docstring): `beyond_rules` — level is `logical`, `domain_rule` or `artifact`, or some reference has no numeric value, or a numeric value is not found in the document; `table_reachable` — level `numeric`/`categorical`, every numeric reference value found in a table under a header that names the field; `text_reachable` — level `numeric`/`categorical`, every value found, but at least one only in text or under another header.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ceiling.py
from src.evaluation.ceiling import ceiling_table, classify_finding
from src.evaluation.schema import Finding, Ref
from src.ingestion.real import Page, PageTable


def page(number, text, rows=None, header=None):
    tables = [PageTable(rows=rows, bbox=(0, 0, 1, 1), header=header)] if rows else []
    return Page(number=number, text=text, lines=[], tables=tables)


def finding(level_type, refs, obj="b1", fld="total_area_m2"):
    return Finding(id="F1", level="numeric", type=level_type, field=fld, object=obj, refs=refs) \
        if level_type != "STATEMENT_CONTRADICTION" else \
        Finding(id="F1", level="logical", type=level_type, field=fld, object=obj, refs=refs)


def test_numeric_finding_with_value_in_header_matched_table_is_table_reachable():
    pages = [page(1, "Общая площадь 1247,79", rows=[["Показатель", "Значение"], ["x", "1247,79"]],
                  header=["Показатель", "Общая площадь"])]
    refs = [Ref(page=1, quote="1247,79", object="b1", value=1247.79)]
    # header regex for total_area_m2 must match "Общая площадь"
    assert classify_finding(finding("TEP_CROSS_SECTION_MISMATCH", refs), pages) == "table_reachable"


def test_value_only_in_text_is_text_reachable():
    pages = [page(1, "площадь здания составляет 1247,79 м2")]
    refs = [Ref(page=1, quote="1247,79", object="b1", value=1247.79)]
    assert classify_finding(finding("TEP_CROSS_SECTION_MISMATCH", refs), pages) == "text_reachable"


def test_logical_level_is_always_beyond_rules():
    pages = [page(1, "текст")]
    refs = [Ref(page=1, quote="текст", object="b1")]
    assert classify_finding(finding("STATEMENT_CONTRADICTION", refs), pages) == "beyond_rules"


def test_numeric_value_not_found_is_beyond_rules():
    pages = [page(1, "ничего похожего")]
    refs = [Ref(page=1, quote="ничего", object="b1", value=999.5)]
    assert classify_finding(finding("TEP_CROSS_SECTION_MISMATCH", refs), pages) == "beyond_rules"


def test_reference_without_numeric_value_is_beyond_rules():
    pages = [page(1, "текст")]
    refs = [Ref(page=1, quote="текст", object="b1")]
    assert classify_finding(finding("TEP_CROSS_SECTION_MISMATCH", refs), pages) == "beyond_rules"


def test_ceiling_table_counts_by_level_and_class():
    pages = [page(1, "1247,79 м2")]
    a = finding("TEP_CROSS_SECTION_MISMATCH", [Ref(page=1, quote="1247,79", object="b1", value=1247.79)])
    b = finding("STATEMENT_CONTRADICTION", [Ref(page=1, quote="1247,79", object="b1")])
    table = ceiling_table([(a, classify_finding(a, pages)), (b, classify_finding(b, pages))])
    assert table["numeric"]["text_reachable"] == 1 and table["logical"]["beyond_rules"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ceiling.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.evaluation.ceiling'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evaluation/ceiling.py
"""RQ1: which annotated findings are reachable at all by comparing extracted numbers?

``beyond_rules``  level is logical / domain_rule / artifact, or a reference has no numeric value, or a numeric
                  reference value is not found anywhere in the document;
``table_reachable`` level numeric / categorical, every numeric reference value sits in a table under a header
                  that names the field (the only case a table extractor can get right);
``text_reachable`` level numeric / categorical, every value is found, but at least one only in running text or
                  under another header.
A value of 0 < |v| < 100 that is an integer is "trivial" for ``extractability.locate`` and counted as found.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from src.evaluation.extractability import locate
from src.evaluation.schema import Finding
from src.ingestion.real import Page
from src.ner.common.taxonomy import Level

REACHABLE_LEVELS = (Level.NUMERIC, Level.CATEGORICAL)


def classify_finding(f: Finding, pages: list[Page]) -> str:
    if f.level not in REACHABLE_LEVELS:
        return "beyond_rules"
    hits = []
    for ref in f.refs:
        if not isinstance(ref.value, int | float) or isinstance(ref.value, bool):
            return "beyond_rules"
        hits.append(locate(pages, ref.object or f.object, f.field, float(ref.value), ref.page))
    if any(h.where == "none" for h in hits):
        return "beyond_rules"
    if all(h.where == "table" and h.column_ok for h in hits):
        return "table_reachable"
    return "text_reachable"


def ceiling_table(findings_classes: list[tuple[Finding, str]]) -> dict[str, dict[str, int]]:
    table: dict[str, Counter] = defaultdict(Counter)
    for f, cls in findings_classes:
        table[f.level.value][cls] += 1
    return {lvl: dict(c) for lvl, c in table.items()}
```

```python
# scripts/exp_e1_ceiling.py
"""E1 (RQ1): ceiling by extractability on annotated real documents.

    uv run python scripts/exp_e1_ceiling.py
Output: build/research/e1_ceiling.json and a markdown table on stdout. Documents whose PDF is absent are skipped.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path  # noqa: E402
from src.evaluation.ceiling import ceiling_table, classify_finding  # noqa: E402
from src.ingestion.real import load_pages  # noqa: E402

OUT = ROOT / "build" / "research"
CLASSES = ("table_reachable", "text_reachable", "beyond_rules")


def main() -> int:
    anns = [load_annotation(p) for p in sorted(ANNOTATIONS_DIR.glob("*.gt.json"))]
    anns = [a for a in anns if source_path(a).exists()]
    if not anns:
        print("no annotated real documents present locally")
        return 1
    all_pairs, per_doc = [], {}
    for ann in anns:
        pages = load_pages(source_path(ann))
        pairs = [(f, classify_finding(f, pages)) for f in ann.findings]
        all_pairs += pairs
        per_doc[ann.document_id] = {f.id: cls for f, cls in pairs}
    table = ceiling_table(all_pairs)
    total = len(all_pairs)
    print(f"documents: {len(anns)}, findings: {total}\n")
    print("| level | " + " | ".join(CLASSES) + " |\n|---|" + "---|" * len(CLASSES))
    for lvl, row in sorted(table.items()):
        print(f"| {lvl} | " + " | ".join(str(row.get(c, 0)) for c in CLASSES) + " |")
    reachable = sum(c != "beyond_rules" for _, c in all_pairs)
    print(f"\nreachable by number comparison: {reachable}/{total}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "e1_ceiling.json").write_text(json.dumps(
        {"documents": len(anns), "findings": total, "table": table, "per_doc": per_doc},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test and the script**

Run: `uv run pytest tests/test_ceiling.py -v`
Expected: PASS (6 passed)

Run: `uv run python scripts/exp_e1_ceiling.py`
Expected: with the one local real document, prints a table with rows per level and writes `build/research/e1_ceiling.json`; without the PDF, prints `no annotated real documents present locally` and exits 1.

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/ceiling.py scripts/exp_e1_ceiling.py tests/test_ceiling.py
git commit -m "E1: потолок по извлекаемости — какие находки достижимы сопоставлением чисел"
```

---

### Task 7: E2 — synthetic versus real gap (RQ2)

**Files:**
- Create: `src/evaluation/gap.py`
- Create: `scripts/exp_e2_gap.py`
- Test: `tests/test_gap.py`

**Interfaces:**
- Consumes: `Scoreboard`, `score_set`, `gt_slots` (`bench.py`); `RulesSystem`; `generate_set`; `match`, `map_objects`; `run_rules`; `load_pages`; `FINAL_SEEDS`, `seed_list`
- Produces:
  - `MISS_CAUSES: tuple[str, ...]` = `("table_format", "object_resolution", "terminology", "language", "ocr", "no_rule", "other")`
  - `load_misses(path: Path) -> dict[str, dict]` (finding id → `{"cause": str, "note": str}`)
  - `summarize_misses(missed_ids: list[str], misses: dict[str, dict]) -> dict[str, int]` (cause counts, `"unlabeled"` for ids without an entry)
  - `choose_scenario(n_real_annotations: int) -> str` → `"A"` if ≥ 5 else `"B"`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gap.py
import json

import pytest

from src.evaluation.gap import MISS_CAUSES, choose_scenario, load_misses, summarize_misses


def test_choose_scenario_threshold():
    assert choose_scenario(0) == "B" and choose_scenario(4) == "B"
    assert choose_scenario(5) == "A" and choose_scenario(12) == "A"


def test_summarize_misses_counts_causes_and_flags_unlabeled():
    misses = {"F1": {"cause": "no_rule", "note": ""}, "F2": {"cause": "table_format", "note": "x"}}
    got = summarize_misses(["F1", "F2", "F3", "F1"], misses)
    assert got == {"no_rule": 2, "table_format": 1, "unlabeled": 1}


def test_load_misses_validates_causes(tmp_path):
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"F1": {"cause": "no_rule", "note": "n"}}), encoding="utf-8")
    assert load_misses(ok)["F1"]["cause"] == "no_rule"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"F1": {"cause": "nonsense", "note": ""}}), encoding="utf-8")
    with pytest.raises(ValueError, match="nonsense"):
        load_misses(bad)


def test_load_misses_missing_file_is_empty(tmp_path):
    assert load_misses(tmp_path / "nope.json") == {}


def test_miss_causes_contains_expected_groups():
    assert {"table_format", "object_resolution", "terminology", "language", "ocr", "no_rule"} <= set(MISS_CAUSES)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.evaluation.gap'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evaluation/gap.py
"""RQ2: bookkeeping for the synthetic-to-real gap: miss causes labelled by hand and the scenario choice."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

MISS_CAUSES = ("table_format", "object_resolution", "terminology", "language", "ocr", "no_rule", "other")
SCENARIO_A_MIN_DOCS = 5


def choose_scenario(n_real_annotations: int) -> str:
    """A: quantitative RQ2 (>= 5 documents); B: qualitative case analysis."""
    return "A" if n_real_annotations >= SCENARIO_A_MIN_DOCS else "B"


def load_misses(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    for fid, entry in data.items():
        if entry.get("cause") not in MISS_CAUSES:
            raise ValueError(f"{fid}: unknown cause {entry.get('cause')!r}, allowed: {MISS_CAUSES}")
    return data


def summarize_misses(missed_ids: list[str], misses: dict[str, dict]) -> dict[str, int]:
    counts = Counter(misses[i]["cause"] if i in misses else "unlabeled" for i in missed_ids)
    return dict(counts)
```

```python
# scripts/exp_e2_gap.py
"""E2 (RQ2): S1 on frozen synthetic seeds versus S1 on annotated real documents.

    uv run python scripts/exp_e2_gap.py --profile v2 --limit 100
Miss causes of real documents are labelled by hand in annotations/real/misses/<doc_id>.json
({"F3": {"cause": "table_format", "note": "..."}}); run once, label the misses, run again.
Output: build/research/e2_gap.json and a markdown summary on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.crossvalidation.rules import run_rules  # noqa: E402
from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path  # noqa: E402
from src.evaluation.bench import Scoreboard, gt_slots, score_set  # noqa: E402
from src.evaluation.gap import choose_scenario, load_misses, summarize_misses  # noqa: E402
from src.evaluation.match import map_objects, match  # noqa: E402
from src.evaluation.protocol import FINAL_SEEDS, PROTOCOL_VERSION, seed_list  # noqa: E402
from src.evaluation.systems import RulesSystem  # noqa: E402
from src.ingestion.real import load_pages  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402

OUT = ROOT / "build" / "research"
MISSES_DIR = ANNOTATIONS_DIR / "misses"  # a subfolder: other tools glob annotations/real/*.json


def f(x: float | None) -> str:
    return "—" if x is None else f"{x:.2f}"


def synthetic(profile: str, limit: int) -> dict:
    system, result = RulesSystem(), {}
    with tempfile.TemporaryDirectory() as tmp:
        for lang in ("ru", "kz"):
            board = Scoreboard()
            for seed in seed_list(FINAL_SEEDS)[:limit]:
                set_dir = generate_set(lang, seed, Path(tmp) / profile, scans=False, profile=profile)
                gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
                got = system.detect(sorted(set_dir.glob("text/*.pdf")), lang)
                board.add(score_set(lang, set_dir.name, gt_slots(gt), got))
            p, r, f1 = board.prf()
            result[lang] = {"precision": p, "recall": r, "f1": f1, "ci": board.bootstrap_f1(),
                            "fp_per_set": board.fp_per_set(),
                            "by_level": {lv: board.prf(level=lv) for lv in
                                         ("numeric", "categorical", "logical", "domain_rule", "artifact")}}
    return result


def real() -> dict:
    anns = [load_annotation(p) for p in sorted(ANNOTATIONS_DIR.glob("*.gt.json"))]
    out = {"n_annotations": len(anns), "scenario": choose_scenario(len(anns)), "documents": {}}
    for ann in anns:
        if not source_path(ann).exists():
            continue
        report = run_rules(load_pages(source_path(ann)))
        res = match(ann.findings, report.findings, map_objects(report.objects, ann.objects))
        misses = load_misses(MISSES_DIR / f"{ann.document_id}.json")
        out["documents"][ann.document_id] = {
            "precision": res.precision, "recall": res.recall, "by_level": res.by_level(),
            "false_positives": len(res.false),
            "miss_causes": summarize_misses([g.id for g in res.missed], misses)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile", default="v2")
    ap.add_argument("--limit", type=int, default=100, help="sets per language (default: all 100)")
    args = ap.parse_args()
    syn, re_ = synthetic(args.profile, args.limit), real()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "e2_gap.json").write_text(json.dumps(
        {"protocol": PROTOCOL_VERSION, "profile": args.profile, "synthetic": syn, "real": re_},
        ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    print(f"scenario {re_['scenario']} ({re_['n_annotations']} annotated real documents)\n")
    print("| source | P | R | F1 | FP/set |\n|---|---|---|---|---|")
    for lang, r in syn.items():
        print(f"| synthetic {lang} | {f(r['precision'])} | {f(r['recall'])} | {f(r['f1'])} | {f(r['fp_per_set'])} |")
    for doc, r in re_["documents"].items():
        print(f"| real {doc} | {f(r['precision'])} | {f(r['recall'])} | — | {r['false_positives']} |")
        print(f"|   miss causes | {r['miss_causes']} | | | |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test and a small script run**

Run: `uv run pytest tests/test_gap.py -v`
Expected: PASS (5 passed)

Run: `uv run python scripts/exp_e2_gap.py --limit 5`
Expected: prints scenario line and a table with two synthetic rows (ru, kz) and one row per locally present real document; writes `build/research/e2_gap.json`.

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/gap.py scripts/exp_e2_gap.py tests/test_gap.py
git commit -m "E2: разрыв синтетика против реальности, причины пропусков и выбор сценария A/B"
```

---

### Task 8: E3 — comparison of S1, L1, H1 (RQ3)

**Files:**
- Create: `scripts/exp_e3_compare.py`
- Create: `src/evaluation/real_llm.py`
- Test: `tests/test_real_llm.py`, `tests/test_e3_runner.py`

**Interfaces:**
- Consumes: `System`, `RulesSystem`, `HybridSystem` (`systems.py`); `LLMSystem`, `AnthropicClient`, `LLMClient`, `build_prompt`, `parse_items` (`llm.py`); `Scoreboard`, `score_set`, `gt_slots`; protocol constants; `Finding`, `Ref` (`schema.py`); `Page` (`ingestion/real.py`)
- Produces:
  - `real_llm.findings_from_items(items: list[dict], pages: list[Page]) -> tuple[list[Finding], dict[str, str]]` (findings plus object-id → name map for `map_objects`); items without a usable `page` and `quote` found on that page are dropped
  - `real_llm.guard_real(allow: bool) -> None` raising `PermissionError("…--allow-real-llm…")` when `allow` is false
  - `exp_e3_compare.run_synthetic(system_factory, lang, seeds, profile, tmp, granularity) -> Scoreboard`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_real_llm.py
import pytest

from src.evaluation.real_llm import findings_from_items, guard_real
from src.ingestion.real import Page


def pages():
    return [Page(number=1, text="Общая площадь здания котельной 100 м2", lines=[], tables=[]),
            Page(number=2, text="Сейсмичность 7 баллов", lines=[], tables=[])]


def test_guard_real_refuses_without_flag():
    with pytest.raises(PermissionError, match="--allow-real-llm"):
        guard_real(False)
    guard_real(True)


def test_findings_need_page_and_quote_present_on_that_page():
    items = [
        {"type": "STATEMENT_CONTRADICTION", "field": "", "object": "Котельная", "page": 2, "evidence": "Сейсмичность 7"},
        {"type": "STATEMENT_CONTRADICTION", "field": "", "object": "Котельная", "page": 1, "evidence": "нет такого"},
        {"type": "STATEMENT_CONTRADICTION", "field": "", "object": "Котельная", "evidence": "Сейсмичность 7"},
    ]
    found, objects = findings_from_items(items, pages())
    assert len(found) == 1 and found[0].refs[0].page == 2
    assert objects[found[0].object] == "Котельная"


def test_findings_level_comes_from_taxonomy():
    items = [{"type": "COPY_PASTE_LABEL", "field": "", "object": "", "page": 1, "evidence": "Общая площадь"}]
    found, _ = findings_from_items(items, pages())
    assert found[0].level.value == "artifact" and found[0].object == "document"
```

```python
# tests/test_e3_runner.py
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exp_e3", ROOT / "scripts" / "exp_e3_compare.py")
exp_e3 = importlib.util.module_from_spec(spec)
sys.modules["exp_e3"] = exp_e3
spec.loader.exec_module(exp_e3)


class PerfectSystem:
    """Returns exactly the ground-truth slots of the set it is asked about (looked up from the directory)."""

    name = "perfect"

    def detect(self, paths, lang):
        import json

        from src.evaluation.bench import gt_slots

        gt = json.loads((paths[0].parent.parent / "ground_truth.json").read_text(encoding="utf-8"))
        return gt_slots(gt)


def test_run_synthetic_scores_every_set_with_perfect_system(tmp_path):
    board = exp_e3.run_synthetic(PerfectSystem(), "ru", [31, 32], "v1", tmp_path, "slot")
    assert len(board.records) == 2
    p, r, f1 = board.prf()
    assert r in (1.0, None) and p in (1.0, None)


def test_mean_sd_of_runs():
    import pytest

    mean, sd = exp_e3.mean_sd([0.5, 0.7, 0.6])
    assert mean == pytest.approx(0.6) and sd == pytest.approx(0.0816497, abs=1e-6)  # population sd
    assert exp_e3.mean_sd([0.5]) == (0.5, 0.0)
    assert exp_e3.mean_sd([]) == (None, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_real_llm.py tests/test_e3_runner.py -v`
Expected: FAIL (`ModuleNotFoundError: src.evaluation.real_llm`, missing `scripts/exp_e3_compare.py`)

- [ ] **Step 3: Write minimal implementation**

```python
# src/evaluation/real_llm.py
"""LLM findings on real documents, in the same ``Finding`` model as the annotation, plus the data-policy guard."""

from __future__ import annotations

from src.evaluation.annotations import norm_ws
from src.evaluation.schema import Finding, Ref
from src.ingestion.real import Page
from src.ner.common.taxonomy import TYPE_LEVEL, DiscrepancyType


def guard_real(allow: bool) -> None:
    if not allow:
        raise PermissionError("real documents are not sent to an LLM without --allow-real-llm (data policy)")


def findings_from_items(items: list[dict], pages: list[Page]) -> tuple[list[Finding], dict[str, str]]:
    """Keep only items that cite a page and a quote that is really on that page."""
    texts = {p.number: norm_ws(p.text) for p in pages}
    findings, objects = [], {}
    for item in items:
        page, quote = item.get("page"), norm_ws(str(item.get("evidence", "")))
        if not isinstance(page, int) or not quote or quote not in texts.get(page, ""):
            continue
        name = str(item.get("object", "")).strip()
        obj = "document" if not name else next((k for k, v in objects.items() if v == name), f"o{len(objects) + 1}")
        if name:
            objects[obj] = name
        dtype = DiscrepancyType(item["type"])
        findings.append(Finding(id=f"L{len(findings) + 1}", level=TYPE_LEVEL[dtype], type=dtype,
                                field=str(item.get("field", "")), object=obj,
                                refs=[Ref(page=page, quote=quote)], note="llm"))
    return findings, objects
```

```python
# scripts/exp_e3_compare.py
"""E3 (RQ3): S1, L1, H1 on frozen synthetic seeds, per language; optional real documents.

    uv run python scripts/exp_e3_compare.py --systems S1 L1 H1 --runs 3 --limit 100
    uv run python scripts/exp_e3_compare.py --systems S1 --real
    uv run python scripts/exp_e3_compare.py --systems S1 L1 H1 --real --allow-real-llm   # data policy: opt in

L1 and H1 share cached LLM answers, so H1 costs nothing extra. Output: build/research/e3_compare.json
(model, prompt version, protocol version and run count are recorded) and a markdown table on stdout.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.crossvalidation.rules import run_rules  # noqa: E402
from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path  # noqa: E402
from src.evaluation.bench import Scoreboard, gt_slots, score_set  # noqa: E402
from src.evaluation.llm import AnthropicClient, LLMSystem  # noqa: E402
from src.evaluation.match import map_objects, match  # noqa: E402
from src.evaluation.protocol import (  # noqa: E402
    FINAL_SEEDS,
    LLM_MODEL,
    LLM_RUNS,
    PROMPT_VERSION,
    PROTOCOL_VERSION,
    seed_list,
)
from src.evaluation.real_llm import guard_real  # noqa: E402
from src.evaluation.systems import HybridSystem, RulesSystem  # noqa: E402
from src.ingestion.real import load_pages  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402

OUT = ROOT / "build" / "research"
LEVELS = ("numeric", "categorical", "logical", "domain_rule", "artifact")


def mean_sd(xs: list[float]) -> tuple[float | None, float | None]:
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    return round(statistics.mean(xs), 10), round(statistics.pstdev(xs), 10) if len(xs) > 1 else 0.0


def run_synthetic(system, lang: str, seeds: list[int], profile: str, tmp: Path, granularity: str) -> Scoreboard:
    board = Scoreboard()
    for seed in seeds:
        set_dir = generate_set(lang, seed, tmp / profile, scans=False, profile=profile)
        gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
        got = system.detect(sorted(set_dir.glob("text/*.pdf")), lang)
        board.add(score_set(lang, set_dir.name, gt_slots(gt), got, granularity))
    return board


def build_systems(names: list[str], run: int, cache: Path | None):
    llm = LLMSystem(AnthropicClient(cache_dir=cache), run=run) if {"L1", "H1"} & set(names) else None
    pool = {"S1": RulesSystem(), "L1": llm}
    pool["H1"] = HybridSystem(pool["S1"], llm) if llm else None
    return {n: pool[n] for n in names}


def evaluate_real(names: list[str], allow_llm: bool) -> dict:
    out = {}
    anns = [load_annotation(p) for p in sorted(ANNOTATIONS_DIR.glob("*.gt.json"))]
    for ann in (a for a in anns if source_path(a).exists()):
        pages = load_pages(source_path(ann))
        for name in names:
            if name != "S1":
                guard_real(allow_llm)
                print(f"{name} on real documents is not implemented yet (see the note below Task 8)", file=sys.stderr)
                continue
            report = run_rules(pages)
            res = match(ann.findings, report.findings, map_objects(report.objects, ann.objects))
            out.setdefault(ann.document_id, {})[name] = {
                "precision": res.precision, "recall": res.recall, "by_level": res.by_level(),
                "false_positives": len(res.false)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--systems", nargs="+", default=["S1"], choices=["S1", "L1", "H1"])
    ap.add_argument("--runs", type=int, default=LLM_RUNS)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--profile", default="v2")
    ap.add_argument("--granularity", choices=["slot", "type"], default="slot")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--allow-real-llm", action="store_true")
    args = ap.parse_args()

    seeds = seed_list(FINAL_SEEDS)[: args.limit]
    cache = OUT / "llm_cache"
    results: dict = {"protocol": PROTOCOL_VERSION, "model": LLM_MODEL, "prompt": PROMPT_VERSION,
                     "runs": args.runs, "granularity": args.granularity, "synthetic": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for name in args.systems:
            runs = args.runs if name in ("L1", "H1") else 1
            for lang in ("ru", "kz"):
                f1s, boards = [], []
                for run in range(runs):
                    system = build_systems([name], run, cache)[name]
                    board = run_synthetic(system, lang, seeds, args.profile, Path(tmp), args.granularity)
                    boards.append(board)
                    f1s.append(board.prf()[2])
                board = boards[0]
                p, r, f1 = board.prf()
                m, sd = mean_sd(f1s)
                results["synthetic"].setdefault(name, {})[lang] = {
                    "precision": p, "recall": r, "f1": f1, "f1_runs_mean": m, "f1_runs_sd": sd,
                    "ci": board.bootstrap_f1(), "fp_per_set": board.fp_per_set(),
                    "by_level": {lv: board.prf(level=lv) for lv in LEVELS}}
    if args.real:
        results["real"] = evaluate_real(args.systems, args.allow_real_llm)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "e3_compare.json").write_text(json.dumps(results, ensure_ascii=False, indent=1, default=list),
                                         encoding="utf-8")
    print("| system | lang | P | R | F1 (CI) | FP/set |\n|---|---|---|---|---|---|")
    for name, langs in results["synthetic"].items():
        for lang, r in langs.items():
            fmt = lambda x: "—" if x is None else f"{x:.2f}"  # noqa: E731
            ci = "—" if r["ci"] is None else f"{r['ci'][0]:.2f}–{r['ci'][1]:.2f}"
            print(f"| {name} | {lang} | {fmt(r['precision'])} | {fmt(r['recall'])} | {fmt(r['f1'])} ({ci}) "
                  f"| {fmt(r['fp_per_set'])} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

> L1/H1 on real documents are deliberately not wired: they need a pages-based prompt that is added only if the data-policy decision allows sending real text to a closed-contour model. Until then `--real` runs S1 and `guard_real` refuses L1/H1 without `--allow-real-llm`; with the flag they are skipped with a message. `findings_from_items` and its tests are ready for that step. If the decision is "allowed", add a task: `LLMSystem.detect_items_pages(pages)` (page markers in the prompt, no cache write) plus a test with `FakeClient`, then call `findings_from_items(items, pages)` in `evaluate_real`.

- [ ] **Step 4: Run tests and a dry experiment**

Run: `uv run pytest tests/test_real_llm.py tests/test_e3_runner.py -v`
Expected: PASS (5 passed)

Run: `uv run python scripts/exp_e3_compare.py --systems S1 --limit 5`
Expected: markdown table with S1 rows for ru and kz; `build/research/e3_compare.json` written.

Run (requires `ANTHROPIC_API_KEY` or the configured base URL): `uv run python scripts/exp_e3_compare.py --systems S1 L1 H1 --runs 1 --limit 3`
Expected: L1 and H1 rows appear; second invocation makes no API calls (cache hit).

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/real_llm.py scripts/exp_e3_compare.py tests/test_real_llm.py tests/test_e3_runner.py
git commit -m "E3: сравнение S1, L1, H1 по языкам и уровням, защита реальных документов от отправки в LLM"
```

---

### Task 9: E4 — package for commercial tools (observation)

**Files:**
- Create: `scripts/exp_e4_prepare.py`
- Create: `docs/research/e4-protocol.md`
- Test: `tests/test_e4_prepare.py`

**Interfaces:**
- Consumes: `generate_set`, `E4_SEEDS`, `seed_list`
- Produces: `prepare(out: Path, langs=("ru", "kz")) -> list[Path]` — for each seed a folder `<out>/<lang>_<seed>/` with `text/*.pdf` copied, `expected.json` (list of `{id, type, field, object}` from ground truth), and a row template in `<out>/observations.csv`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_e4_prepare.py
import csv
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exp_e4", ROOT / "scripts" / "exp_e4_prepare.py")
exp_e4 = importlib.util.module_from_spec(spec)
sys.modules["exp_e4"] = exp_e4
spec.loader.exec_module(exp_e4)


def test_prepare_writes_pdfs_expected_and_observation_template(tmp_path, monkeypatch):
    monkeypatch.setattr(exp_e4, "SEEDS", [9000, 9001])
    dirs = exp_e4.prepare(tmp_path, langs=("ru",))
    assert [d.name for d in dirs] == ["ru_9000", "ru_9001"]
    assert sorted(p.stem for p in (dirs[0] / "text").glob("*.pdf")) == ["AR", "KR", "PZ", "SMETA"]
    expected = json.loads((dirs[0] / "expected.json").read_text(encoding="utf-8"))
    assert all({"id", "type", "field", "object"} <= set(e) for e in expected)
    rows = list(csv.DictReader((tmp_path / "observations.csv").open(encoding="utf-8")))
    assert {r["set"] for r in rows} == {"ru_9000", "ru_9001"}
    assert set(rows[0]) == {"set", "tool", "found_types", "false_alarms", "evidence_given", "language_ok", "notes"}


def test_prepare_does_not_ship_ground_truth_to_tool_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(exp_e4, "SEEDS", [9000])
    (d,) = exp_e4.prepare(tmp_path, langs=("kz",))
    assert not (d / "text" / "ground_truth.json").exists()
    assert not list(d.glob("**/ground_truth.json"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_e4_prepare.py -v`
Expected: FAIL (`FileNotFoundError` for `scripts/exp_e4_prepare.py`)

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/exp_e4_prepare.py
"""E4: prepare the synthetic package for commercial tools and a template for manual observations.

    uv run python scripts/exp_e4_prepare.py --out build/research/e4
Give only ``<set>/text/*.pdf`` to a tool (synthetic data only); ``expected.json`` stays with you.
Fill ``observations.csv`` by hand while running Armeta / Norma.AI on a free trial (see docs/research/e4-protocol.md).
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.protocol import E4_SEEDS, seed_list  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402

SEEDS = seed_list(E4_SEEDS)
TOOLS = ("Armeta", "Norma.AI")
COLUMNS = ["set", "tool", "found_types", "false_alarms", "evidence_given", "language_ok", "notes"]


def prepare(out: Path, langs=("ru", "kz")) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    dirs, rows = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for lang in langs:
            for seed in SEEDS:
                src = generate_set(lang, seed, Path(tmp), scans=False, profile="v2")
                dst = out / f"{lang}_{seed}"
                (dst / "text").mkdir(parents=True, exist_ok=True)
                for pdf in sorted(src.glob("text/*.pdf")):
                    shutil.copy(pdf, dst / "text" / pdf.name)
                gt = json.loads((src / "ground_truth.json").read_text(encoding="utf-8"))
                expected = [{"id": d["id"], "type": d["type"], "field": d["field"], "object": d.get("object", "")}
                            for d in gt["discrepancies"]]
                (dst / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
                dirs.append(dst)
                rows += [{"set": dst.name, "tool": t} for t in TOOLS]
    with (out / "observations.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows({c: r.get(c, "") for c in COLUMNS} for r in rows)
    return dirs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "research" / "e4")
    args = ap.parse_args()
    dirs = prepare(args.out)
    print(f"prepared {len(dirs)} sets in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

```markdown
<!-- docs/research/e4-protocol.md -->
# E4: наблюдение за коммерческими инструментами

Только синтетика, только бесплатный триал. Реальные документы в сервисы не загружаются.

1. `uv run python scripts/exp_e4_prepare.py` готовит 20 наборов на язык в `build/research/e4/`.
2. В инструмент загружается только `text/*.pdf` набора; `expected.json` остаётся у вас.
3. Для каждой пары «набор, инструмент» заполняется строка `observations.csv`:
   - `found_types` — какие из ожидаемых типов из `expected.json` инструмент показал (через `;`);
   - `false_alarms` — число замечаний, которых нет в `expected.json` и которые нельзя оправдать текстом;
   - `evidence_given` — `yes` / `no`: указано ли место в документе;
   - `language_ok` — `yes` / `no` / `n/a`: корректно ли обработан казахский набор;
   - `notes` — версия или дата триала, ограничения тарифа, что не удалось загрузить.
4. В тексте диплома результат описывается качественно (что находит, что нет, есть ли доказательство). F1 по этим
   данным не считается: выборка маленькая, продукты закрыты, версии меняются.
5. Если у инструмента нет бесплатного доступа или он не принимает казахский, это записывается в `notes` и в выводы.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_e4_prepare.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/exp_e4_prepare.py docs/research/e4-protocol.md tests/test_e4_prepare.py
git commit -m "E4: набор для коммерческих инструментов и шаблон наблюдений"
```

---

### Task 10: Run order, full test pass and results hand-off

**Files:**
- Create: `docs/research/runbook.md`

- [ ] **Step 1: Full test suite and lint**

Run: `uv run pytest -q && uv run ruff check src scripts tests`
Expected: all tests pass (real-PDF tests may skip), ruff reports no errors. Fix anything reported before continuing.

- [ ] **Step 2: Write the runbook**

```markdown
<!-- docs/research/runbook.md -->
# Порядок запуска экспериментов

Перед первым запуском E2/E3 заморозьте код: коммит с тегом `protocol-v1`. После заморозки правила, `match.py`
и `protocol.py` не меняются; иначе поднимите `PROTOCOL_VERSION` и перезапустите всё.

| Шаг | Команда | Результат |
|---|---|---|
| E1 | `uv run python scripts/exp_e1_ceiling.py` | `build/research/e1_ceiling.json` |
| E2 | `uv run python scripts/exp_e2_gap.py` (потом разметить промахи в `annotations/real/misses/<id>.json` и запустить снова) | `build/research/e2_gap.json` |
| E3 | `uv run python scripts/exp_e3_compare.py --systems S1 L1 H1 --runs 3` | `build/research/e3_compare.json` |
| E3 (грубая метрика) | то же с `--granularity type` | отдельный прогон, кэш LLM переиспользуется |
| E4 | `uv run python scripts/exp_e4_prepare.py`, затем ручной прогон по `docs/research/e4-protocol.md` | `build/research/e4/observations.csv` |

LLM-прогоны требуют доступа к API; ответы кэшируются в `build/research/llm_cache/`, повторный запуск бесплатен.
Файлы в `build/` не коммитятся. Таблицы для текста диплома берутся из JSON и stdout этих скриптов.
```

- [ ] **Step 3: Commit**

```bash
git add docs/research/runbook.md
git commit -m "Порядок запуска экспериментов E1–E4"
```

---

## Self-review (done at writing time)

- **Spec coverage:** §3 RQ1 → Task 6; RQ2 → Task 7 (scenario A/B, miss causes); RQ3 → Tasks 2–5, 8; §4 systems S1/L1/H1/C1 → Tasks 3, 4, 5, 9; B0 is the extraction-only regex baseline (`scripts/regex_baseline.py`, already present): it has no detection output, so it appears only in the extraction comparison and is not a `System`; §5 data and seeds → Task 1; §6 metrics (P/R/F1 by level, language, type; FP per set; bootstrap) → Task 2; the share of findings with evidence (page and quote) and time/cost per document are NOT implemented (see gaps); §7 E1–E4 → Tasks 6–9; §8 threats → recorded fields (model, prompt, protocol version) in result files; §9 artifacts → scripts, docs, runbook.
- **Known gaps against the spec, to decide before execution:** (1) B0 is not a `System` (reason above). (2) L1/H1 on real documents are gated and not implemented until the data-policy decision (note in Task 8). (3) Evidence share, time and cost per document are not measured (add token counts to `AnthropicClient` and an evidence counter if the thesis needs them). (4) The second-annotator agreement from spec §5 is manual and has no task.
- **Placeholders:** none; every code step contains the code.
- **Type consistency:** `Slot`, `slot`, `gt_slots`, `score_set`, `Scoreboard.prf/bootstrap_f1/fp_per_set`, `System.detect`, `LLMSystem.detect_items`, `HybridSystem`, `findings_from_items`, `guard_real` are named identically in every task that uses them.
