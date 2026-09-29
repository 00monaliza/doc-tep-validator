"""Matching predicted findings against manual ground truth of a real document.

A prediction matches a ground-truth finding if both have the same ``type``, the
same object (after mapping predicted object ids to annotation ids) and at least
one reference on the same page. Matching is one-to-one, greedy in GT order.

Predicted objects are named by the rules themselves (``obj1`` =
"Здание цеха"); they are mapped to annotation objects by name: shared word
stems or an abbreviation of one name equal to the other's id.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from src.evaluation.schema import Finding
from src.ner.common.taxonomy import Level

RESERVED = ("site", "document", "all")


def _stems(name: str) -> set[str]:
    words = [w.lower() for w in re.split(r"[\s\-–]+", name) if len(w) >= 3]
    return {w[: max(3, min(7, len(w) - 2))] for w in words}


def _abbrev(name: str) -> str:
    words = [w for w in re.split(r"[\s\-–]+", name) if w]
    return "".join(w[0] for w in words).lower() if len(words) >= 2 else ""


def map_objects(pred: dict[str, str], gt: dict[str, str]) -> dict[str, str]:
    mapping = {k: k for k in pred if k in RESERVED and k in gt}
    scores = []
    for pid, pname in pred.items():
        if pid in mapping:
            continue
        for gid, gname in gt.items():
            if gid in RESERVED:
                continue
            score = len(_stems(pname) & _stems(gname))
            if _abbrev(pname) and _abbrev(pname) in (gid.lower(), _abbrev(gname)):
                score += 2
            if pname.strip().lower() == gname.strip().lower():
                score += 10
            if score:
                scores.append((score, pid, gid))
    used = set()
    for _, pid, gid in sorted(scores, reverse=True):
        if pid not in mapping and gid not in used:
            mapping[pid] = gid
            used.add(gid)
    return mapping


@dataclass
class MatchResult:
    pairs: list[tuple[Finding, Finding]] = field(default_factory=list)  # (gt, pred)
    missed: list[Finding] = field(default_factory=list)
    false: list[Finding] = field(default_factory=list)

    @property
    def precision(self) -> float | None:
        n = len(self.pairs) + len(self.false)
        return len(self.pairs) / n if n else None

    @property
    def recall(self) -> float | None:
        n = len(self.pairs) + len(self.missed)
        return len(self.pairs) / n if n else None

    def by_level(self) -> dict[str, dict[str, int]]:
        table = {lvl.value: Counter() for lvl in Level}
        for gt, _ in self.pairs:
            table[gt.level.value]["found"] += 1
        for gt in self.missed:
            table[gt.level.value]["missed"] += 1
        for p in self.false:
            table[p.level.value]["false"] += 1
        return {lvl: {k: c[k] for k in ("found", "missed", "false")} for lvl, c in table.items()}


def match(gt: list[Finding], pred: list[Finding], object_map: dict[str, str]) -> MatchResult:
    result = MatchResult()
    free = list(pred)
    for g in gt:
        g_pages = {r.page for r in g.refs}
        hit = next((p for p in free if p.type == g.type and object_map.get(p.object, p.object) == g.object
                    and g_pages & {r.page for r in p.refs}), None)
        if hit is None:
            result.missed.append(g)
        else:
            free.remove(hit)
            result.pairs.append((g, hit))
    result.false = free
    return result
