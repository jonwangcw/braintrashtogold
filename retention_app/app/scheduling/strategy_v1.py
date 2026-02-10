from datetime import datetime, timedelta

from app.scheduling.strategy_base import ScheduleDecision


SCHEDULE_INTERVALS = [1, 1, 1, 3, 5, 7, 7, 14]


def next_state(
    step_index: int,
    last_completed_at: datetime,
    last_score: float,
    scheduled_attempt_count: int,
) -> ScheduleDecision:
    if last_score <= 5:
        return ScheduleDecision(
            next_due_at=datetime.utcnow() + timedelta(days=1),
            next_step_index=0,
            terminate=False,
            reset_questions=True,
        )

    base_interval = SCHEDULE_INTERVALS[min(step_index, len(SCHEDULE_INTERVALS) - 1)]
    if last_score >= 8 and scheduled_attempt_count >= 3:
        base_interval += 2

    next_due = last_completed_at + timedelta(days=base_interval)
    next_step_index = step_index + 1
    if next_step_index > 7:
        return ScheduleDecision(
            next_due_at=None,
            next_step_index=7,
            terminate=True,
            reset_questions=False,
        )

    return ScheduleDecision(
        next_due_at=next_due,
        next_step_index=next_step_index,
        terminate=False,
        reset_questions=False,
    )
