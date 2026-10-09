"""Download the label-embedding model into the Hugging Face cache (once; the only step that needs network).

    uv run python scripts/fetch_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from huggingface_hub import snapshot_download  # noqa: E402

from src.ner.common.label_embed import MODEL_ID  # noqa: E402

if __name__ == "__main__":
    print(snapshot_download(MODEL_ID, allow_patterns=["*.json", "*.safetensors", "sentencepiece.bpe.model"]))
