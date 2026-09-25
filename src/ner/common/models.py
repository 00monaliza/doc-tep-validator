"""Registry of pretrained encoders used as NER backbones.

Hub ids were verified against the HuggingFace Hub API on 2026-09-25; see
README § "Модели" for the search log. Kazakh: no ISSAI kazBERT/kazRoBERTa
encoder is published under the `issai` organisation, so the default KZ
backbone is the multilingual fallback XLM-RoBERTa (temporary, see README).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Backbone:
    hub_id: str
    lang: str
    license: str
    note: str


BACKBONES: dict[str, Backbone] = {
    "ru": Backbone(
        hub_id="cointegrated/rubert-tiny2",
        lang="ru",
        license="mit",
        note="Small Russian BERT (29M params, 2048 ctx); fast to fine-tune on MPS.",
    ),
    "kz": Backbone(
        hub_id="FacebookAI/xlm-roberta-base",
        lang="multilingual (incl. kk)",
        license="mit",
        note="TEMPORARY multilingual fallback: no ISSAI kazBERT/kazRoBERTa encoder on the Hub.",
    ),
}

# Kazakh candidates found on the Hub, to evaluate against the fallback later.
# None of these is an ISSAI-published encoder.
KZ_CANDIDATES: dict[str, str] = {
    "kz-transformers/kaz-roberta-conversational":
        "Monolingual Kazakh RoBERTa-base (MLM), Apache-2.0, org kz-transformers (not ISSAI).",
    "yeshpanovrustem/xlm-roberta-large-kaznerd":
        "XLM-R large fine-tuned for NER on KazNERD (ISSAI dataset, LREC 2022); CC-BY-4.0, 560M params.",
}

# ISSAI resources that ARE on the Hub and relevant to NER.
ISSAI_DATASETS: dict[str, str] = {
    "issai/kaznerd": "KazNERD — Kazakh NER dataset (ISSAI, LREC 2022), 25 entity classes.",
}
