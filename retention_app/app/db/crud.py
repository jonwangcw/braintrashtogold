from datetime import datetime

from sqlalchemy.orm import Session

from . import models


def create_content(session: Session, title: str, content_type: models.ContentType, source_url: str) -> models.Content:
    content = models.Content(
        title=title,
        content_type=content_type,
        source_url=source_url,
        status=models.ContentStatus.pending,
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
