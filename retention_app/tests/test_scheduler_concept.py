from datetime import datetime, timedelta

from app.scheduling.bloom_ladder import adjust_bloom_stage
from app.scheduling.strategy_base import ConceptReviewResult, ConceptScheduleState
from app.scheduling.strategy_concept import next_state


def test_concept_strategy_updates_ef_and_interval_deterministically():
    reviewed_at = datetime(2024, 1, 10, 8, 0, 0)
    state = ConceptScheduleState(
        ease_factor=2.5,
        interval_days=6,
        lapses=0,
        repetitions=2,
        bloom_stage=0,
    )
    review = ConceptReviewResult(
        reviewed_at=reviewed_at,
        comfort=3,
        difficulty_llm=0.2,
    )

    decision = next_state(state, review)

    assert decision.ease_factor == 2.6
    assert decision.repetitions == 3
    assert decision.lapses == 0
    assert decision.interval_days == 16
    assert decision.next_due_at == reviewed_at + timedelta(days=16)


def test_concept_strategy_lapse_resets_repetitions_and_clamps_ef():
    reviewed_at = datetime(2024, 1, 10, 8, 0, 0)
    state = ConceptScheduleState(
        ease_factor=1.4,
        interval_days=20,
        lapses=1,
        repetitions=4,
        bloom_stage=2,
    )
    review = ConceptReviewResult(
        reviewed_at=reviewed_at,
        comfort=0,
        difficulty_llm=1.0,
    )

    decision = next_state(state, review)

    assert decision.ease_factor == 1.3
    assert decision.repetitions == 0
    assert decision.lapses == 2
    assert decision.interval_days == 1


def test_concept_strategy_applies_bloom_weight_and_interval_clamp():
    reviewed_at = datetime(2024, 1, 10, 8, 0, 0)
    state = ConceptScheduleState(
        ease_factor=2.6,
        interval_days=170,
        lapses=0,
        repetitions=5,
        bloom_stage=5,
    )
    review = ConceptReviewResult(
        reviewed_at=reviewed_at,
        comfort=3,
        difficulty_llm=0.0,
        bloom_weight=1.2,
    )

    decision = next_state(state, review)

    assert decision.interval_days == 180
    assert decision.next_due_at == reviewed_at + timedelta(days=180)


def test_bloom_ladder_promotes_with_high_comfort_and_correctness():
    decision = adjust_bloom_stage(
        current_stage=1,
        recent_comfort=[3, 3, 2],
        recent_correct=[True, True, True],
    )
    assert decision.action == "promote"
    assert decision.next_stage == 2


def test_bloom_ladder_demotes_with_low_comfort_or_correctness():
    low_comfort_decision = adjust_bloom_stage(
        current_stage=3,
        recent_comfort=[1, 1, 1],
    )
    assert low_comfort_decision.action == "demote"
    assert low_comfort_decision.next_stage == 2

    low_correctness_decision = adjust_bloom_stage(
        current_stage=3,
        recent_comfort=[3, 3, 2],
        recent_correct=[True, False, False],
    )
    assert low_correctness_decision.action == "demote"
    assert low_correctness_decision.next_stage == 2


def test_bloom_ladder_holds_when_signals_are_mixed():
    decision = adjust_bloom_stage(
        current_stage=2,
        recent_comfort=[2, 2, 1],
        recent_correct=[True, True, False],
    )
    assert decision.action == "hold"
    assert decision.next_stage == 2
