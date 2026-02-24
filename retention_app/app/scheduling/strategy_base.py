from dataclasses import dataclass
from datetime import datetime


@dataclass
class ScheduleDecision:
    next_due_at: datetime | None
    next_step_index: int
    terminate: bool


def next_state(
    step_index: int,
    last_completed_at: datetime,
    comfort_level: int,
    scheduled_attempt_count: int,
) -> ScheduleDecision:
    raise NotImplementedError
