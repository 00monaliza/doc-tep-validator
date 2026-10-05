"""E3 (RQ3): S1, L1, H1 on frozen synthetic seeds, per language; optional real documents.

    uv run python scripts/exp_e3_compare.py --systems S1 L1 H1 --runs 3 --limit 100
    uv run python scripts/exp_e3_compare.py --systems S1 --real
    uv run python scripts/exp_e3_compare.py --systems S1 L1 H1 --real --allow-real-llm   # data policy: opt in

L1 and H1 share cached LLM answers, so H1 costs nothing extra. Output: build/research/e3_compare.json
(model, prompt version, protocol version and run count are recorded) and a markdown table on stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.crossvalidation.rules import run_rules  # noqa: E402
from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path  # noqa: E402
from src.evaluation.bench import Scoreboard, gt_slots, score_set  # noqa: E402
from src.evaluation.llm import AnthropicClient, LLMSystem  # noqa: E402
from src.evaluation.match import map_objects, match  # noqa: E402
from src.evaluation.protocol import (  # noqa: E402
    LLM_MODEL,
    LLM_RUNS,
    PROMPT_VERSION,
    PROTOCOL_VERSION,
    resolve_seeds,
)
from src.evaluation.real_llm import guard_real  # noqa: E402
from src.evaluation.systems import HybridSystem, RulesSystem  # noqa: E402
from src.ingestion.real import load_pages  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402

OUT = ROOT / "build" / "research"
LEVELS = ("numeric", "categorical", "logical", "domain_rule", "artifact")


def has_llm_credentials(env) -> bool:
    return bool(env.get("ANTHROPIC_API_KEY") or env.get("ANTHROPIC_AUTH_TOKEN"))


def mean_sd(xs: list[float]) -> tuple[float | None, float | None]:
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    return round(statistics.mean(xs), 10), round(statistics.pstdev(xs), 10) if len(xs) > 1 else 0.0


def run_synthetic(system, lang: str, seeds: list[int], profile: str, tmp: Path, granularity: str) -> Scoreboard:
    board = Scoreboard()
    for seed in seeds:
        set_dir = generate_set(lang, seed, tmp / profile, scans=False, profile=profile)
        gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
        got = system.detect(sorted(set_dir.glob("text/*.pdf")), lang)
        board.add(score_set(lang, set_dir.name, gt_slots(gt), got, granularity))
    return board


def build_systems(names: list[str], run: int, cache: Path | None):
    llm = LLMSystem(AnthropicClient(cache_dir=cache), run=run) if {"L1", "H1"} & set(names) else None
    pool = {"S1": RulesSystem(), "L1": llm}
    pool["H1"] = HybridSystem(pool["S1"], llm) if llm else None
    return {n: pool[n] for n in names}


def evaluate_real(names: list[str], allow_llm: bool) -> dict:
    out = {}
    anns = [load_annotation(p) for p in sorted(ANNOTATIONS_DIR.glob("*.gt.json"))]
    for ann in (a for a in anns if source_path(a).exists()):
        pages = load_pages(source_path(ann))
        for name in names:
            if name != "S1":
                guard_real(allow_llm)
                print(f"{name} on real documents is not implemented yet (see the note below Task 8)", file=sys.stderr)
                continue
            report = run_rules(pages)
            res = match(ann.findings, report.findings, map_objects(report.objects, ann.objects))
            out.setdefault(ann.document_id, {})[name] = {
                "precision": res.precision, "recall": res.recall, "by_level": res.by_level(),
                "false_positives": len(res.false)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--systems", nargs="+", default=["S1"], choices=["S1", "L1", "H1"])
    ap.add_argument("--runs", type=int, default=LLM_RUNS)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--seeds", default=None, help="smoke runs only, e.g. 31-35; default: the frozen final seeds")
    ap.add_argument("--profile", default="v2")
    ap.add_argument("--granularity", choices=["slot", "type"], default="slot")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--allow-real-llm", action="store_true")
    args = ap.parse_args()
    if {"L1", "H1"} & set(args.systems) and not has_llm_credentials(os.environ):
        print("L1/H1 need ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN) in the environment; nothing was run",
              file=sys.stderr)
        return 2

    seeds = resolve_seeds(args.seeds)[: args.limit]
    cache = OUT / "llm_cache"
    results: dict = {"protocol": PROTOCOL_VERSION, "model": LLM_MODEL, "prompt": PROMPT_VERSION,
                     "runs": args.runs, "granularity": args.granularity, "synthetic": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for name in args.systems:
            runs = args.runs if name in ("L1", "H1") else 1
            for lang in ("ru", "kz"):
                f1s, boards = [], []
                for run in range(runs):
                    system = build_systems([name], run, cache)[name]
                    board = run_synthetic(system, lang, seeds, args.profile, Path(tmp), args.granularity)
                    boards.append(board)
                    f1s.append(board.prf()[2])
                board = boards[0]
                p, r, f1 = board.prf()
                m, sd = mean_sd(f1s)
                results["synthetic"].setdefault(name, {})[lang] = {
                    "precision": p, "recall": r, "f1": f1, "f1_runs_mean": m, "f1_runs_sd": sd,
                    "ci": board.bootstrap_f1(), "fp_per_set": board.fp_per_set(),
                    "by_level": {lv: board.prf(level=lv) for lv in LEVELS}}
    if args.real:
        results["real"] = evaluate_real(args.systems, args.allow_real_llm)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "e3_compare.json").write_text(json.dumps(results, ensure_ascii=False, indent=1, default=list),
                                         encoding="utf-8")
    print("| system | lang | P | R | F1 (CI) | FP/set |\n|---|---|---|---|---|---|")
    for name, langs in results["synthetic"].items():
        for lang, r in langs.items():
            fmt = lambda x: "—" if x is None else f"{x:.2f}"  # noqa: E731
            ci = "—" if r["ci"] is None else f"{r['ci'][0]:.2f}–{r['ci'][1]:.2f}"
            print(f"| {name} | {lang} | {fmt(r['precision'])} | {fmt(r['recall'])} | {fmt(r['f1'])} ({ci}) "
                  f"| {fmt(r['fp_per_set'])} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
