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
from src.evaluation.protocol import LLM_EFFORT, LLM_MAX_TOKENS, LLM_MODEL, PROMPT_VERSION
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


def _find_answer_list(raw: str) -> list | None:
    """The JSON array of the answer, skipping brackets in prose: first list made only of objects, else first list."""
    decoder, fallback = json.JSONDecoder(), None
    for match in re.finditer(r"\[", raw):
        try:
            data, _ = decoder.raw_decode(raw[match.start():])
        except json.JSONDecodeError:
            continue
        if not isinstance(data, list):
            continue
        if all(isinstance(d, dict) for d in data):
            return data
        fallback = fallback if fallback is not None else data
    return fallback


def parse_items(raw: str) -> tuple[list[dict], int]:
    """Valid items (known ``type``) and the number of dropped or unparseable entries."""
    data = _find_answer_list(raw)
    if data is None:
        return [], 1
    items = [d for d in data if isinstance(d, dict) and isinstance(d.get("type"), str) and d["type"] in KNOWN_TYPES]
    return items, len(data) - len(items)


class AnthropicClient:
    def __init__(self, model: str = LLM_MODEL, cache_dir: Path | None = None, max_tokens: int = LLM_MAX_TOKENS,
                 effort: str = LLM_EFFORT, api=None):
        if api is None:
            import anthropic

            api = anthropic.Anthropic()
        self._api = api
        self.uncached = 0  # answers not cached because the turn did not end normally (truncated, refused)
        self.model, self.cache_dir, self.max_tokens, self.effort = model, cache_dir, max_tokens, effort

    def _cache_path(self, system: str, user: str, run: int) -> Path | None:
        if self.cache_dir is None:
            return None
        key = f"{self.model}|{self.effort}|{self.max_tokens}|{PROMPT_VERSION}|{run}|{system}|{user}"
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def complete(self, system: str, user: str, run: int = 0) -> str:
        path = self._cache_path(system, user, run)
        if path is not None and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["text"]
        reply = self._api.messages.create(model=self.model, max_tokens=self.max_tokens, system=system,
                                          output_config={"effort": self.effort},
                                          messages=[{"role": "user", "content": user}])
        # A refusal or an empty turn has no text block: the caller counts it as a parse failure.
        text = "".join(block.text for block in reply.content if block.type == "text")
        if reply.stop_reason != "end_turn":
            self.uncached += 1  # max_tokens cut-off or refusal: never cache, so a rerun can succeed
        elif path is not None:
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
        return {slot(i["type"], str(i.get("field") or "")) for i in self.detect_items(paths)}
