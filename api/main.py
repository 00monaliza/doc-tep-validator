"""Placeholder FastAPI app for the future demo (run: uv run uvicorn api.main:app --reload)."""

from fastapi import FastAPI

from src.ner.common.models import BACKBONES
from src.ner.common.taxonomy import DiscrepancyType

app = FastAPI(title="doc-tep-validator")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "discrepancy_types": [t.value for t in DiscrepancyType],
        "backbones": {lang: b.hub_id for lang, b in BACKBONES.items()},
    }
