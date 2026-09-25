"""Turn a text-layer PDF into a 'scanned' image-only PDF (for the OCR path).

Degradations (Pillow + numpy): small skew, uneven brightness/contrast, Gaussian
blur, Gaussian noise, dust specks and JPEG compression. Parameters are drawn
per page from the set's RNG and returned so they can be stored in ground truth.
"""

from __future__ import annotations

import io
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from src.ingestion.common.pdf import rasterize


def degrade(page: Image.Image, rng: random.Random) -> tuple[Image.Image, dict]:
    params = {
        "rotation_deg": round(rng.uniform(-1.2, 1.2), 3),
        "blur_radius": round(rng.uniform(0.4, 0.9), 3),
        "noise_sigma": round(rng.uniform(5, 12), 2),
        "brightness": round(rng.uniform(0.92, 1.03), 3),
        "contrast": round(rng.uniform(0.85, 1.05), 3),
        "specks": rng.randint(150, 600),
        "jpeg_quality": rng.randint(60, 80),
    }
    img = page.convert("L").rotate(params["rotation_deg"], resample=Image.BICUBIC, fillcolor=255)
    img = ImageEnhance.Brightness(img).enhance(params["brightness"])
    img = ImageEnhance.Contrast(img).enhance(params["contrast"])
    img = img.filter(ImageFilter.GaussianBlur(params["blur_radius"]))

    nprng = np.random.default_rng(rng.getrandbits(32))
    arr = np.asarray(img, dtype=np.float32)
    arr += nprng.normal(0, params["noise_sigma"], arr.shape)
    ys = nprng.integers(0, arr.shape[0], params["specks"])
    xs = nprng.integers(0, arr.shape[1], params["specks"])
    arr[ys, xs] = nprng.uniform(0, 90, params["specks"])
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "L")

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=params["jpeg_quality"])
    return Image.open(io.BytesIO(buf.getvalue())).convert("L"), params


def make_scan(text_pdf: Path, out_pdf: Path, rng: random.Random, dpi: int = 200) -> tuple[list[Path], list[dict]]:
    """Write per-page JPEGs next to `out_pdf` and an image-only PDF; return (pages, params)."""
    pages, params = [], []
    for i, page in enumerate(rasterize(text_pdf, dpi=dpi), start=1):
        img, p = degrade(page, rng)
        path = out_pdf.with_name(f"{out_pdf.stem}_p{i}.jpg")
        img.save(path, "JPEG", quality=p["jpeg_quality"], dpi=(dpi, dpi))
        pages.append(path)
        params.append({"page": i, "dpi": dpi} | p)
    images = [Image.open(p) for p in pages]
    images[0].save(out_pdf, "PDF", resolution=dpi, save_all=True, append_images=images[1:])
    return pages, params
