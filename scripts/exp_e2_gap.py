"""E2 (RQ2): S1 on frozen synthetic seeds versus S1 on annotated real documents.

    uv run python scripts/exp_e2_gap.py --profile v2 --limit 100
Miss causes of real documents are labelled by hand in annotations/real/misses/<doc_id>.json
({"F3": {"cause": "table_format", "note": "..."}}); run once, label the misses, run again.
Output: build/research/e2_gap.json and a markdown summary on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.crossvalidation.rules import run_rules  # noqa: E402
from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path  # noqa: E402
from src.evaluation.bench import Scoreboard, gt_slots, score_set  # noqa: E402
from src.evaluation.gap import choose_scenario, load_misses, summarize_misses  # noqa: E402
from src.evaluation.match import map_objects, match  # noqa: E402
from src.evaluation.protocol import PROTOCOL_VERSION, resolve_seeds, result_name  # noqa: E402
from src.evaluation.systems import RulesSystem  # noqa: E402
from src.ingestion.real import load_pages  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402

OUT = ROOT / "build" / "research"
MISSES_DIR = ANNOTATIONS_DIR / "misses"  # a subfolder: other tools glob annotations/real/*.json


def f(x: float | None) -> str:
    return "—" if x is None else f"{x:.2f}"


def synthetic(profile: str, limit: int, spec: str | None) -> dict:
    system, result = RulesSystem(), {}
    with tempfile.TemporaryDirectory() as tmp:
        for lang in ("ru", "kz"):
            board = Scoreboard()
            for seed in resolve_seeds(spec)[:limit]:
                set_dir = generate_set(lang, seed, Path(tmp) / profile, scans=False, profile=profile)
                gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
                got = system.detect(sorted(set_dir.glob("text/*.pdf")), lang)
                board.add(score_set(lang, set_dir.name, gt_slots(gt), got))
            result[lang] = board.summary()
    return result


def real() -> dict:
    anns = [load_annotation(p) for p in sorted(ANNOTATIONS_DIR.glob("*.gt.json"))]
    out = {"n_annotations": len(anns), "scenario": choose_scenario(len(anns)), "documents": {}}
    for ann in anns:
        if not source_path(ann).exists():
            continue
        report = run_rules(load_pages(source_path(ann)))
        res = match(ann.findings, report.findings, map_objects(report.objects, ann.objects))
        misses = load_misses(MISSES_DIR / f"{ann.document_id}.json")
        out["documents"][ann.document_id] = {
            "precision": res.precision, "recall": res.recall, "by_level": res.by_level(),
            "false_positives": len(res.false),
            "miss_causes": summarize_misses([g.id for g in res.missed], misses)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile", default="v2")
    ap.add_argument("--limit", type=int, default=100, help="sets per language (default: all 100)")
    ap.add_argument("--seeds", default=None, help="smoke runs only, e.g. 31-35; default: the frozen final seeds")
    args = ap.parse_args()
    syn, re_ = synthetic(args.profile, args.limit, args.seeds), real()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / result_name("e2_gap", args.seeds, args.limit)).write_text(json.dumps(
        {"protocol": PROTOCOL_VERSION, "profile": args.profile, "seeds": args.seeds or "final", "limit": args.limit,
         "matching": {"synthetic": "slot (type, field); object and page ignored",
                      "real": "src/evaluation/match.py: type + object + page; field ignored"},
         "synthetic": syn, "real": re_},
        ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    print(f"scenario {re_['scenario']} ({re_['n_annotations']} annotated real documents)\n")
    print("| source | P | R | F1 | FP/set |\n|---|---|---|---|---|")
    for lang, r in syn.items():
        print(f"| synthetic {lang} | {f(r['precision'])} | {f(r['recall'])} | {f(r['f1'])} | {f(r['fp_per_set'])} |")
    for doc, r in re_["documents"].items():
        print(f"| real {doc} | {f(r['precision'])} | {f(r['recall'])} | — | {r['false_positives']} |")
        print(f"|   miss causes | {r['miss_causes']} | | | |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
