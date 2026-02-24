from datetime import datetime, timedelta

import pytest

from app.scheduling.strategy_v1 import next_state


def test_scheduler_uses_daily_spacing_for_first_three_attempts():
    last_completed = datetime(2024, 1, 1)
    decision = next_state(1, last_completed, comfort_level=5, scheduled_attempt_count=2)
    assert decision.next_due_at == last_completed + timedelta(days=1)


def test_scheduler_uses_comfort_spacing_starting_attempt_four():
    last_completed = datetime(2024, 1, 1)
    decision = next_state(3, last_completed, comfort_level=4, scheduled_attempt_count=3)
    assert decision.next_due_at == last_completed + timedelta(days=4)


def test_scheduler_terminates_after_eighth_scheduled_attempt():
    last_completed = datetime(2024, 1, 1)
    decision = next_state(7, last_completed, comfort_level=3, scheduled_attempt_count=7)
    assert decision.terminate is True
    assert decision.next_due_at is None


@pytest.mark.parametrize("comfort_level", [0, 6])
def test_scheduler_rejects_invalid_comfort(comfort_level: int):
    with pytest.raises(ValueError, match="comfort_level must be between 1 and 5"):
        next_state(2, datetime(2024, 1, 1), comfort_level=comfort_level, scheduled_attempt_count=2)
