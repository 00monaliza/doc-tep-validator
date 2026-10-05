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

LLM_MODEL = "claude-sonnet-5-5"
PROMPT_VERSION = "p1"
LLM_RUNS = 3


def seed_list(span: tuple[int, int]) -> list[int]:
    return list(range(span[0], span[1] + 1))
