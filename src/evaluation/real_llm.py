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
