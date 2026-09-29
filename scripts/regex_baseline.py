"""Naive regex baseline: is the synthetic corpus still trivially easy?

Exactly the check that gave 75/75 on v1: on the ПЗ text layer after
``re.sub(r"\\s+", " ", text)`` two patterns (total area and building area rows
of the ТЭП table) are searched and compared with ground truth
``tep.PZ.<field>`` to 1e-6. Only fields present in ground truth are counted
(a deliberately missing TEP is not a slot). The KZ patterns are the literal
analogues and were not part of the original check.

    uv run python scripts/regex_baseline.py --seeds 5001-5040 --lang ru --profile v1 v2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion.common import pdf  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402

NUM = r"(\d{1,3}(?: \d{3})*(?:,\d+)?)"
PATTERNS = {
    "ru": {"total_area_m2": re.compile(rf"Общая площадь здания\s+м²\s+{NUM}"),
           "building_area_m2": re.compile(rf"Площадь застройки\s+м²\s+{NUM}")},
    "kz": {"total_area_m2": re.compile(rf"Ғимараттың жалпы ауданы\s+м²\s+{NUM}"),
           "building_area_m2": re.compile(rf"Құрылыс салу ауданы\s+м²\s+{NUM}")},
}


def to_float(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def regex_extract(text: str, lang: str) -> dict[str, float]:
    text = re.sub(r"\s+", " ", text)
    out = {}
    for fld, rx in PATTERNS[lang].items():
        m = rx.search(text)
        if m:
            out[fld] = to_float(m.group(1))
    return out


def seeds(spec: str) -> list[int]:
    lo, _, hi = spec.partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", default="5001-5040")
    ap.add_argument("--lang", nargs="+", default=["ru", "kz"])
    ap.add_argument("--profile", nargs="+", default=["v1", "v2"])
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        for profile in args.profile:
            for lang in args.lang:
                ok = total = 0
                per = {f: [0, 0] for f in PATTERNS[lang]}
                for seed in seeds(args.seeds):
                    set_dir = generate_set(lang, seed, Path(tmp) / profile, scans=False, profile=profile)
                    gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
                    found = regex_extract(pdf.extract_text(set_dir / "text" / "PZ.pdf"), lang)
                    for fld in PATTERNS[lang]:
                        gold = gt["tep"]["PZ"][fld]["value"]
                        if gold is None:
                            continue
                        hit = fld in found and abs(found[fld] - gold) < 1e-6
                        per[fld][0] += hit
                        per[fld][1] += 1
                        ok, total = ok + hit, total + 1
                fields = ", ".join(f"{f} {a}/{b}" for f, (a, b) in per.items())
                print(f"{profile} {lang}: {ok}/{total} = {ok / total:.0%}   ({fields})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
