"""Tesseract OCR wrapper with explicit language-data resolution.

Homebrew's `tesseract` formula ships only `eng`/`osd`. Russian and Kazakh data
come from `brew install tesseract-lang` (system-wide) or from the project-local
copy in assets/tessdata/ (fetched by scripts/fetch_assets.sh). The system
installation is preferred; the local one is used as a fallback so the pipeline
works without touching the system.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytesseract
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_TESSDATA = PROJECT_ROOT / "assets" / "tessdata"

# Our language codes -> Tesseract traineddata names.
TESS_LANG = {"ru": "rus", "kz": "kaz"}
BREW_INSTALL_HINT = "brew install tesseract-lang"


@dataclass(frozen=True)
class TessLangSource:
    lang: str  # tesseract code, e.g. "kaz"
    tessdata_dir: Path | None  # None -> system default dir
    origin: str  # "system" | "project-local"


def system_languages() -> set[str]:
    if shutil.which("tesseract") is None:
        return set()
    out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    return {line.strip() for line in out.splitlines()[1:] if line.strip()}


def local_languages() -> set[str]:
    if not LOCAL_TESSDATA.is_dir():
        return set()
    return {p.stem for p in LOCAL_TESSDATA.glob("*.traineddata")}


def resolve_language(tess_lang: str) -> TessLangSource:
    """Find where `tess_lang` traineddata lives; raise with an install hint if nowhere."""
    if tess_lang in system_languages():
        return TessLangSource(tess_lang, None, "system")
    if tess_lang in local_languages():
        return TessLangSource(tess_lang, LOCAL_TESSDATA, "project-local")
    raise RuntimeError(
        f"Tesseract language '{tess_lang}' not found (system or {LOCAL_TESSDATA}). "
        f"Install system-wide: `{BREW_INSTALL_HINT}`, or run scripts/fetch_assets.sh."
    )


def ocr_image(image: Image.Image, lang: str, psm: int = 6) -> str:
    """OCR a PIL image. `lang` is our code ("ru"/"kz") or a raw tesseract code."""
    src = resolve_language(TESS_LANG.get(lang, lang))
    config = f"--psm {psm}"
    if src.tessdata_dir is not None:
        config += f' --tessdata-dir "{src.tessdata_dir}"'
    return pytesseract.image_to_string(image, lang=src.lang, config=config)
