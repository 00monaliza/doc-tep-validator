"""Text/table extraction from PDFs (text layer) and rasterisation for the OCR path."""

from __future__ import annotations

from pathlib import Path

import pdfplumber
import pymupdf
from PIL import Image


def extract_text(path: str | Path) -> str:
    """Text layer via pdfplumber, pages joined with form feeds."""
    with pdfplumber.open(path) as pdf:
        return "\f".join(page.extract_text() or "" for page in pdf.pages)


def extract_tables(path: str | Path) -> list[list[list[str | None]]]:
    with pdfplumber.open(path) as pdf:
        return [table for page in pdf.pages for table in page.extract_tables()]


def rasterize(path: str | Path, dpi: int = 300, grayscale: bool = True) -> list[Image.Image]:
    """Render every page to a PIL image with PyMuPDF."""
    colorspace = pymupdf.csGRAY if grayscale else pymupdf.csRGB
    images = []
    with pymupdf.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi, colorspace=colorspace)
            mode = "L" if grayscale else "RGB"
            images.append(Image.frombytes(mode, (pix.width, pix.height), pix.samples))
    return images


def has_text_layer(path: str | Path) -> bool:
    return bool(extract_text(path).strip())
