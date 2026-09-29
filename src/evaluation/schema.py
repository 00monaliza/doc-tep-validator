"""Pydantic schema of the manual annotation of real documents.

One JSON per document under ``annotations/real/``. Findings use taxonomy v2
(``DiscrepancyType`` + ``Level``); every reference points to a 1-based page and
an exact quote from that page's ``pdfplumber`` text (whitespace-normalized).
The rule-based checker emits findings in the same ``Finding`` model so the two
can be matched directly.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.ner.common.taxonomy import TYPE_LEVEL, DiscrepancyType, Level

Value = float | int | bool | str | list[float | int | bool | str]
Confidence = Literal["certain", "needs_expert"]


class Ref(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    quote: str = Field(min_length=1)
    object: str | None = None
    value: Value | None = None
    unit: str | None = None
    section: str | None = None
    row: str | None = None
    col: str | None = None
    derived: str | None = None
    normalize_whitespace: bool | None = None
    occurrences: int | None = Field(default=None, ge=1)  # expected count of the quote on the page


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    level: Level
    type: DiscrepancyType
    field: str
    object: str
    refs: list[Ref] = Field(min_length=1)
    confidence: Confidence = "certain"
    delta_rel: float | None = None
    note: str = ""

    @model_validator(mode="after")
    def _level_matches_type(self) -> Finding:
        expected = TYPE_LEVEL[self.type]
        if self.level != expected:
            raise ValueError(f"{self.id}: level {self.level} does not match type {self.type} (expected {expected})")
        return self


class RealAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    document_id: str
    source_file: str
    lang: Literal["ru", "kz"]
    doc_type: str
    year: int | None = None
    pages: int = Field(ge=1)
    text_layer: bool
    extractor: str = ""
    objects: dict[str, str]
    # tep[object][field] -> value | [values seen in the document]; "page" is a hint
    tep: dict[str, dict[str, Any]] = {}
    findings: list[Finding]
    annotator: str = ""
    status: Literal["draft", "verified"] = "draft"

    @model_validator(mode="after")
    def _consistent(self) -> RealAnnotation:
        ids = [f.id for f in self.findings]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate finding ids")
        for f in self.findings:
            for obj in [f.object, *(r.object for r in f.refs if r.object)]:
                if obj not in self.objects:
                    raise ValueError(f"{f.id}: unknown object {obj!r}")
            for r in f.refs:
                if r.page > self.pages:
                    raise ValueError(f"{f.id}: page {r.page} > {self.pages}")
        unknown = set(self.tep) - set(self.objects)
        if unknown:
            raise ValueError(f"tep: unknown objects {sorted(unknown)}")
        return self
