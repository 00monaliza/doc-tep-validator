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
