from datetime import datetime, timedelta

import pytest

from sqlalchemy.orm import Session

from app.db import models
from app.db.engine import Base, SessionLocal, engine
from app.services.quiz_service import complete_quiz_attempt


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

        completed = complete_quiz_attempt(session, attempt.id, comfort_rating=4)
        state = session.get(models.ScheduleState, content.id)

    assert completed.submitted_at is not None
    assert completed.total_score == 8.0
    assert state is not None
    assert state.last_score == 8.0


def test_complete_practice_quiz_does_not_require_comfort_or_update_schedule():
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
        session.commit()
        session.refresh(attempt)

        completed = complete_quiz_attempt(session, attempt.id)
        state = session.get(models.ScheduleState, content.id)

    assert completed.submitted_at is not None
    assert completed.total_score is None
    assert state is None
