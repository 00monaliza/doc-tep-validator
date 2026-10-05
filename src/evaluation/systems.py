"""Compared systems behind one interface: a package of PDFs in, a set of detected slots out."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.evaluation.bench import Slot, slot
from src.ner.common.taxonomy import TYPE_LEVEL, DiscrepancyType, Level
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


class HybridSystem:
    """H1: rules own the numeric core; the LLM contributes only the levels rules cannot reach."""

    name = "H1"

    def __init__(self, rules: System, llm, llm_levels: tuple[Level, ...] = (Level.LOGICAL, Level.ARTIFACT)):
        self.rules, self.llm, self.llm_levels = rules, llm, llm_levels

    def detect(self, paths: list[Path], lang: str) -> set[Slot]:
        got = set(self.rules.detect(paths, lang))
        for item in self.llm.detect_items(paths):
            if TYPE_LEVEL[DiscrepancyType(item["type"])] in self.llm_levels:
                got.add(slot(item["type"], str(item.get("field") or "")))
        return got
