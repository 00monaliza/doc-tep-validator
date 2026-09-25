"""Tesseract OCR wrapper (the only OCR engine: EasyOCR has no Kazakh, see README).

Russian/Kazakh traineddata come from `brew install tesseract-lang`.
"""

from __future__ import annotations

import shutil
import subprocess

import pytesseract
from PIL import Image

# Our language codes -> Tesseract traineddata names.
TESS_LANG = {"ru": "rus", "kz": "kaz"}
BREW_INSTALL_HINT = "brew install tesseract-lang"


def system_languages() -> set[str]:
    if shutil.which("tesseract") is None:
        return set()
    out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    return {line.strip() for line in out.splitlines()[1:] if line.strip()}


def resolve_language(lang: str) -> str:
    """Map "ru"/"kz" (or a raw tesseract code) to an installed tesseract language."""
    tess_lang = TESS_LANG.get(lang, lang)
    if tess_lang not in system_languages():
        raise RuntimeError(f"Tesseract language '{tess_lang}' is not installed: run `{BREW_INSTALL_HINT}`.")
    return tess_lang


def ocr_image(image: Image.Image, lang: str, psm: int = 6) -> str:
    """OCR a PIL image. `lang` is our code ("ru"/"kz") or a raw tesseract code."""
    return pytesseract.image_to_string(image, lang=resolve_language(lang), config=f"--psm {psm}")
