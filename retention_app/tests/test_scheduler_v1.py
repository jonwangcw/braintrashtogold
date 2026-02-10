from datetime import datetime, timedelta

from app.scheduling.strategy_v1 import next_state


def test_scheduler_applies_bonus_after_three_attempts():
    last_completed = datetime(2024, 1, 1)
    decision = next_state(3, last_completed, last_score=8, scheduled_attempt_count=3)
    assert decision.next_due_at == last_completed + timedelta(days=5)


def test_scheduler_resets_on_low_score():
    last_completed = datetime(2024, 1, 1)
    decision = next_state(2, last_completed, last_score=5, scheduled_attempt_count=2)
    assert decision.next_step_index == 0
    assert decision.reset_questions is True


def test_scheduler_terminates_after_final_step():
    last_completed = datetime(2024, 1, 1)
    decision = next_state(7, last_completed, last_score=7, scheduled_attempt_count=8)
    assert decision.terminate is True
    assert decision.next_due_at is None
