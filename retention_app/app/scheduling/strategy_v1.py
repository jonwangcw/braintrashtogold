from datetime import datetime, timedelta

from app.scheduling.strategy_base import ScheduleDecision


MAX_SCHEDULED_ATTEMPTS = 8


def _validate_comfort_level(comfort_level: int) -> None:
    if comfort_level < 1 or comfort_level > 5:
        raise ValueError("comfort_level must be between 1 and 5")


def next_state(
    step_index: int,
    last_completed_at: datetime,
    comfort_level: int,
    scheduled_attempt_count: int,
) -> ScheduleDecision:
    _validate_comfort_level(comfort_level)

    current_attempt_number = scheduled_attempt_count + 1
    if current_attempt_number <= 3:
        interval_days = 1
    else:
        interval_days = comfort_level

    next_due = last_completed_at + timedelta(days=interval_days)
    next_step_index = step_index + 1
    if next_step_index >= MAX_SCHEDULED_ATTEMPTS:
        return ScheduleDecision(
            next_due_at=None,
            next_step_index=MAX_SCHEDULED_ATTEMPTS - 1,
            terminate=True,
        )

    return ScheduleDecision(
        next_due_at=next_due,
        next_step_index=next_step_index,
        terminate=False,
    )
