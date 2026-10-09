"""Sentence embeddings of TEP labels: multilingual-e5-small, from local files only.

The weights are fetched once by ``scripts/fetch_models.py``; at run time nothing
goes to the network (real documents never leave the machine).
"""

from __future__ import annotations

from functools import cache

MODEL_ID = "intfloat/multilingual-e5-small"


class LabelEmbedder:
    def __init__(self, model_id: str = MODEL_ID) -> None:
        self.model_id = model_id
        self._tok = self._model = None
        self.error: str | None = None
        self._cache: dict = {}  # text -> embedding

    def available(self) -> bool:
        if self._model is None and self.error is None:
            try:
                from transformers import AutoModel, AutoTokenizer

                self._tok = AutoTokenizer.from_pretrained(self.model_id, local_files_only=True)
                self._model = AutoModel.from_pretrained(self.model_id, local_files_only=True).eval()
            except Exception as e:  # weights not downloaded, broken cache
                self.error = f"{type(e).__name__}: {e}"
        return self._model is not None

    def embed(self, texts: list[str]):
        """L2-normalised mean-pooled embeddings, one row per text (cached per text)."""
        import torch

        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            batch = self._tok([f"query: {t}" for t in missing], padding=True, truncation=True, max_length=64,
                              return_tensors="pt")
            with torch.no_grad():
                hidden = self._model(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1).float()
            vecs = torch.nn.functional.normalize((hidden * mask).sum(1) / mask.sum(1), dim=-1)
            self._cache.update(zip(missing, vecs, strict=True))
        return torch.stack([self._cache[t] for t in texts])


@cache
def get_embedder() -> LabelEmbedder:
    return LabelEmbedder()
