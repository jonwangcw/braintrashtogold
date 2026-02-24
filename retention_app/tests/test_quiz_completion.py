from datetime import datetime, timedelta

import pytest

from sqlalchemy.orm import Session

from app.db import models
from app.db.engine import Base, SessionLocal, engine
from app.services.quiz_service import complete_practice_quiz_attempt, complete_scheduled_quiz_attempt


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _seed_content(session: Session) -> models.Content:
    content = models.Content(
        title="Example",
        content_type=models.ContentType.webpage,
        source_url="https://example.com",
        status=models.ContentStatus.ready,
    )
    session.add(content)
    session.flush()
    return content


def test_complete_scheduled_quiz_updates_schedule_state_with_comfort():
    with SessionLocal() as session:
        content = _seed_content(session)
        qset = models.QuestionSet(
            content_id=content.id,
            kind=models.QuestionSetKind.scheduled,
            generator_model="test",
            generation_prompt_version="v1",
        )
        session.add(qset)
        session.flush()

        attempt = models.QuizAttempt(
            content_id=content.id,
            question_set_id=qset.id,
            kind=models.QuizAttemptKind.scheduled,
        )
        session.add(attempt)
        session.add(
            models.ScheduleState(
                content_id=content.id,
                step_index=0,
                next_due_at=datetime.utcnow() + timedelta(days=1),
                is_terminated=False,
            )
        )
        session.commit()
        session.refresh(attempt)

        completed = complete_scheduled_quiz_attempt(session, attempt.id, comfort_rating=4)
        state = session.get(models.ScheduleState, content.id)

    assert completed.submitted_at is not None
    assert completed.total_score == 8.0
    assert completed.comfort_rating == 4
    assert completed.scheduled_attempt_index == 1
    assert state is not None
    assert state.last_score == 8.0
    assert state.last_scheduled_quiz_at is not None


def test_complete_practice_quiz_does_not_update_schedule():
    with SessionLocal() as session:
        content = _seed_content(session)
        qset = models.QuestionSet(
            content_id=content.id,
            kind=models.QuestionSetKind.practice,
            generator_model="test",
            generation_prompt_version="v1",
        )
        session.add(qset)
        session.flush()

        attempt = models.QuizAttempt(
            content_id=content.id,
            question_set_id=qset.id,
            kind=models.QuizAttemptKind.practice,
        )
        session.add(attempt)
        session.add(
            models.ScheduleState(
                content_id=content.id,
                step_index=2,
                next_due_at=datetime.utcnow() + timedelta(days=3),
                last_scheduled_quiz_at=datetime.utcnow(),
                last_score=6,
                is_terminated=False,
            )
        )
        session.commit()
        session.refresh(attempt)

        completed = complete_practice_quiz_attempt(session, attempt.id)
        state = session.get(models.ScheduleState, content.id)

    assert completed.submitted_at is not None
    assert completed.total_score is None
    assert completed.comfort_rating is None
    assert state is not None
    assert state.step_index == 2


def test_repeat_scheduled_submission_is_idempotent():
    with SessionLocal() as session:
        content = _seed_content(session)
        qset = models.QuestionSet(
            content_id=content.id,
            kind=models.QuestionSetKind.scheduled,
            generator_model="test",
            generation_prompt_version="v1",
        )
        session.add(qset)
        session.flush()

        attempt = models.QuizAttempt(
            content_id=content.id,
            question_set_id=qset.id,
            kind=models.QuizAttemptKind.scheduled,
        )
        session.add(attempt)
        state = models.ScheduleState(
            content_id=content.id,
            step_index=0,
            next_due_at=datetime.utcnow() + timedelta(days=1),
            is_terminated=False,
        )
        session.add(state)
        session.commit()

        first = complete_scheduled_quiz_attempt(session, attempt.id, comfort_rating=3)
        first_submitted_at = first.submitted_at
        first_step = session.get(models.ScheduleState, content.id).step_index

        second = complete_scheduled_quiz_attempt(session, attempt.id, comfort_rating=5)
        second_step = session.get(models.ScheduleState, content.id).step_index

    assert first_submitted_at is not None
    assert second.submitted_at == first_submitted_at
    assert second.comfort_rating == 3
    assert second.total_score == 6.0
    assert first_step == second_step == 1


def test_scheduled_attempt_index_counts_prior_submitted_attempts():
    with SessionLocal() as session:
        content = _seed_content(session)
        qset = models.QuestionSet(
            content_id=content.id,
            kind=models.QuestionSetKind.scheduled,
            generator_model="test",
            generation_prompt_version="v1",
        )
        session.add(qset)
        session.flush()

        previous = models.QuizAttempt(
            content_id=content.id,
            question_set_id=qset.id,
            kind=models.QuizAttemptKind.scheduled,
            submitted_at=datetime.utcnow(),
            total_score=6.0,
            comfort_rating=3,
            scheduled_attempt_index=1,
        )
        current = models.QuizAttempt(
            content_id=content.id,
            question_set_id=qset.id,
            kind=models.QuizAttemptKind.scheduled,
        )
        session.add_all([previous, current])
        session.add(
            models.ScheduleState(
                content_id=content.id,
                step_index=1,
                next_due_at=datetime.utcnow() + timedelta(days=1),
                is_terminated=False,
            )
        )
        session.commit()

        completed = complete_scheduled_quiz_attempt(session, current.id, comfort_rating=4)

    assert completed.scheduled_attempt_index == 2
