from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.scheduling.strategy_base import (
    ConceptReviewResult,
    ConceptScheduleDecision,
    ConceptScheduleState,
)


COMFORT_TO_QUALITY = {
    0: 0,
    1: 3,
    2: 4,
    3: 5,
}

BLOOM_INTERVAL_WEIGHTS = {
    0: 1.00,
    1: 1.05,
    2: 1.10,
    3: 1.18,
    4: 1.25,
    5: 1.33,
}


@dataclass(frozen=True)
class ConceptStrategyConfig:
    min_ease_factor: float = 1.3
    min_interval_days: int = 1
    max_interval_days: int = 180


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _difficulty_factor(difficulty_llm: float) -> float:
    # Higher LLM-estimated difficulty shortens the next interval.
    normalized = _clamp(difficulty_llm, 0.0, 1.0)
    return _clamp(1.1 - (normalized * 0.4), 0.7, 1.1)


def _next_ease_factor(previous_ease_factor: float, quality: int, min_ease_factor: float) -> float:
    delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    return max(min_ease_factor, previous_ease_factor + delta)


def _quality_from_comfort(comfort: int) -> int:
    if comfort not in COMFORT_TO_QUALITY:
        raise ValueError("comfort must be between 0 and 3")
    return COMFORT_TO_QUALITY[comfort]


def next_state(
    state: ConceptScheduleState,
    review: ConceptReviewResult,
    config: ConceptStrategyConfig | None = None,
) -> ConceptScheduleDecision:
    effective_config = config or ConceptStrategyConfig()
    quality = _quality_from_comfort(review.comfort)

    next_ease_factor = _next_ease_factor(state.ease_factor, quality, effective_config.min_ease_factor)

    if quality < 3:
        interval_days = effective_config.min_interval_days
        repetitions = 0
        lapses = state.lapses + 1
    else:
        lapses = state.lapses
        repetitions = state.repetitions + 1
        if repetitions == 1:
            interval_days = 1
        elif repetitions == 2:
            interval_days = 6
        else:
            interval_days = int(round(state.interval_days * next_ease_factor))

    bloom_weight = BLOOM_INTERVAL_WEIGHTS.get(state.bloom_stage, 1.0) * review.bloom_weight
    difficulty = _difficulty_factor(review.difficulty_llm)

    adjusted_interval = int(round(interval_days * difficulty * bloom_weight))
    clamped_interval = max(
        effective_config.min_interval_days,
        min(effective_config.max_interval_days, adjusted_interval),
    )

    return ConceptScheduleDecision(
        next_due_at=review.reviewed_at + timedelta(days=clamped_interval),
        ease_factor=next_ease_factor,
        interval_days=clamped_interval,
        lapses=lapses,
        repetitions=repetitions,
        bloom_stage=state.bloom_stage,
    )
