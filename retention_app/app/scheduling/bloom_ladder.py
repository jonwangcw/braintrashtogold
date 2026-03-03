from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean


BLOOM_STAGES = ["remember", "understand", "apply", "analyze", "evaluate", "create"]


@dataclass(frozen=True)
class BloomLadderDecision:
    next_stage: int
    action: str  # promote | hold | demote


def adjust_bloom_stage(
    current_stage: int,
    recent_comfort: list[int],
    recent_correct: list[bool] | None = None,
    min_stage: int = 0,
    max_stage: int | None = None,
) -> BloomLadderDecision:
    """Promote/hold/demote a concept's Bloom stage from recent review quality."""
    if not recent_comfort:
        return BloomLadderDecision(next_stage=current_stage, action="hold")

    bounded_max = len(BLOOM_STAGES) - 1 if max_stage is None else max_stage
    bounded_max = max(min_stage, bounded_max)

    avg_comfort = fmean(recent_comfort)
    correctness_ratio = None
    if recent_correct:
        correctness_ratio = sum(1 for value in recent_correct if value) / len(recent_correct)

    should_demote = avg_comfort <= 1.25 or (correctness_ratio is not None and correctness_ratio < 0.6)
    should_promote = avg_comfort >= 2.5 and (
        correctness_ratio is None or correctness_ratio >= 0.8
    )

    if should_demote:
        return BloomLadderDecision(next_stage=max(min_stage, current_stage - 1), action="demote")
    if should_promote:
        return BloomLadderDecision(next_stage=min(bounded_max, current_stage + 1), action="promote")
    return BloomLadderDecision(next_stage=current_stage, action="hold")
