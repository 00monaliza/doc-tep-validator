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
