from datetime import datetime

from sqlalchemy.orm import Session

from . import models


def get_or_create_user(session: Session, username: str) -> models.User:
    user = session.query(models.User).filter(models.User.username == username).first()
    if user is None:
        user = models.User(username=username)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def create_content(
    session: Session,
    title: str,
    content_type: models.ContentType,
    source_url: str,
    user_id: int | None = None,
) -> models.Content:
    content = models.Content(
        title=title,
        content_type=content_type,
        source_url=source_url,
        status=models.ContentStatus.pending,
        user_id=user_id,
    )
    session.add(content)
    session.commit()
    session.refresh(content)
    return content


def set_content_ready(session: Session, content: models.Content) -> None:
    content.status = models.ContentStatus.ready
    session.add(content)
    session.commit()


def set_content_error(session: Session, content: models.Content, message: str) -> None:
    content.status = models.ContentStatus.error
    content.error_message = message
    session.add(content)
    session.commit()


def init_schedule_state(session: Session, content_id: int, next_due_at: datetime) -> models.ScheduleState:
    state = models.ScheduleState(
        content_id=content_id,
        step_index=0,
        next_due_at=next_due_at,
        is_terminated=False,
    )
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def get_concept_schedule(
    session: Session, user_id: int, concept_id: int
) -> models.ConceptSchedule | None:
    return (
        session.query(models.ConceptSchedule)
        .filter(
            models.ConceptSchedule.user_id == user_id,
            models.ConceptSchedule.concept_id == concept_id,
        )
        .first()
    )


def create_or_update_concept_schedule(
    session: Session,
    *,
    user_id: int,
    concept_id: int,
    due_at: datetime,
    ease_factor: float = 2.5,
    interval_days: int = 0,
    lapses: int = 0,
    repetitions: int = 0,
    bloom_stage: models.BloomLevel = models.BloomLevel.knowledge,
    last_reviewed_at: datetime | None = None,
) -> models.ConceptSchedule:
    schedule = get_concept_schedule(session, user_id=user_id, concept_id=concept_id)
    if schedule is None:
        schedule = models.ConceptSchedule(
            user_id=user_id,
            concept_id=concept_id,
            due_at=due_at,
            ease_factor=ease_factor,
            interval_days=interval_days,
            lapses=lapses,
            repetitions=repetitions,
            bloom_stage=bloom_stage,
            last_reviewed_at=last_reviewed_at,
        )
    else:
        schedule.due_at = due_at
        schedule.ease_factor = ease_factor
        schedule.interval_days = interval_days
        schedule.lapses = lapses
        schedule.repetitions = repetitions
        schedule.bloom_stage = bloom_stage
        schedule.last_reviewed_at = last_reviewed_at

    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


def update_concept_schedule(
    session: Session,
    schedule: models.ConceptSchedule,
    *,
    due_at: datetime | None = None,
    ease_factor: float | None = None,
    interval_days: int | None = None,
    lapses: int | None = None,
    repetitions: int | None = None,
    bloom_stage: models.BloomLevel | None = None,
    last_reviewed_at: datetime | None = None,
) -> models.ConceptSchedule:
    if due_at is not None:
        schedule.due_at = due_at
    if ease_factor is not None:
        schedule.ease_factor = ease_factor
    if interval_days is not None:
        schedule.interval_days = interval_days
    if lapses is not None:
        schedule.lapses = lapses
    if repetitions is not None:
        schedule.repetitions = repetitions
    if bloom_stage is not None:
        schedule.bloom_stage = bloom_stage
    if last_reviewed_at is not None:
        schedule.last_reviewed_at = last_reviewed_at

    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


def log_review_event(
    session: Session,
    *,
    user_id: int,
    concept_id: int,
    self_comfort: int,
    question_probe_id: int | None = None,
    is_correct: bool | None = None,
    created_at: datetime | None = None,
) -> models.ReviewEvent:
    event = models.ReviewEvent(
        user_id=user_id,
        concept_id=concept_id,
        question_probe_id=question_probe_id,
        self_comfort=self_comfort,
        is_correct=is_correct,
        created_at=created_at or datetime.utcnow(),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
