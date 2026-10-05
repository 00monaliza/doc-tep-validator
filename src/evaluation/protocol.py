"""Frozen evaluation protocol of the research experiments (spec 2026-10-05-research-design.md).

Changing anything here after the first run of E2/E3 invalidates the comparison: bump ``PROTOCOL_VERSION``
and rerun every experiment.
"""

from __future__ import annotations

PROTOCOL_VERSION = "1"

# Seeds the rules were developed on or already evaluated on (README): never use them for final numbers.
SEEN_SEEDS: tuple[tuple[int, int], ...] = ((1, 200), (2000, 2009), (3000, 3049), (5001, 5040), (6000, 6049),
                                           (7000, 7099))
FINAL_SEEDS = (8000, 8099)  # E2 and E3, 100 sets per language
E4_SEEDS = (9000, 9019)  # E4, 20 sets per language, given to commercial tools

LLM_MODEL = "claude-opus-5-5"
LLM_EFFORT = "high"  # Opus 5.5 defaults to medium: pin it
LLM_MAX_TOKENS = 16000
PROMPT_VERSION = "p1"
LLM_RUNS = 3


def seed_list(span: tuple[int, int]) -> list[int]:
    return list(range(span[0], span[1] + 1))


def resolve_seeds(spec: str | None) -> list[int]:
    """``None`` means the frozen final seeds; ``"lo-hi"`` or ``"n"`` is for smoke runs on other seeds."""
    if spec is None:
        return seed_list(FINAL_SEEDS)
    lo, _, hi = spec.partition("-")
    return seed_list((int(lo), int(hi or lo)))


def result_name(stem: str, seeds_spec: str | None, limit: int) -> str:
    """Result file name; smoke runs (other seeds or fewer than the full final set) never overwrite final results."""
    full = seeds_spec is None and limit >= len(seed_list(FINAL_SEEDS))
    return f"{stem}.json" if full else f"{stem}.smoke.json"
