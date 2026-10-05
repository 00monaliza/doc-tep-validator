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
