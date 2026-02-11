from dataclasses import dataclass
from datetime import datetime


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
