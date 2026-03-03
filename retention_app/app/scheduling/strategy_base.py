from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ConceptScheduleState:
    """Mutable concept-level spaced-repetition state persisted between reviews."""

    ease_factor: float
    interval_days: int
    lapses: int
    repetitions: int
    bloom_stage: int


@dataclass(frozen=True)
class ConceptReviewResult:
    """Inputs captured from a completed review used to advance schedule state."""

    reviewed_at: datetime
    comfort: int
    difficulty_llm: float
    bloom_weight: float = 1.0
    correct: bool | None = None


@dataclass(frozen=True)
class ConceptScheduleDecision:
    next_due_at: datetime
    ease_factor: float
    interval_days: int
    lapses: int
    repetitions: int
    bloom_stage: int


class ConceptSchedulingStrategy(Protocol):
    def next_state(
        self,
        state: ConceptScheduleState,
        review: ConceptReviewResult,
    ) -> ConceptScheduleDecision:
        ...


# Backward-compatible contract retained for existing v1 schedule usage.
@dataclass
class ScheduleDecision:
    next_due_at: datetime | None
    next_step_index: int
    terminate: bool
    reset_questions: bool


def next_state(
    step_index: int,
    last_completed_at: datetime,
    last_score: float,
    scheduled_attempt_count: int,
) -> ScheduleDecision:
    raise NotImplementedError
