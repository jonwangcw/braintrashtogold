from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.scheduling.notifications import (
    reminder_body,
    reminder_subject,
    send_email_reminder,
    system_notify,
)


class ReminderScheduler:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.scheduler = BackgroundScheduler(timezone=settings.timezone)

    def start(self) -> None:
        self.scheduler.add_job(self.check_due_items, "interval", minutes=5)
        self.scheduler.start()

    def shutdown(self) -> None:
        self.scheduler.shutdown()

    def check_due_items(self) -> None:
        with self.session_factory() as session:
            due_items = (
                session.query(models.ScheduleState)
                .join(models.Content)
                .filter(models.ScheduleState.is_terminated.is_(False))
                .filter(models.ScheduleState.next_due_at <= datetime.utcnow())
                .all()
            )
            for state in due_items:
                self._send_notifications(session, state)

    def _send_notifications(self, session: Session, state: models.ScheduleState) -> None:
        content = session.get(models.Content, state.content_id)
        if not content:
            return
        url = f"{settings.app_base_url}/content/{content.id}"
        subject = reminder_subject(content.title)
        body = reminder_body(content.title, url)
        session.add(
            models.Notification(
                content_id=content.id,
                kind=models.NotificationKind.email,
                scheduled_for=datetime.utcnow(),
                status=models.NotificationStatus.pending,
            )
        )
        session.commit()
        session.refresh(content)
        session.commit()
        session.expire_all()
        session.close()
        # send outside of db transaction
        session = self.session_factory()
        session.close()
        # async email not awaited here; in real app integrate async loop
        try:
            import asyncio

            asyncio.run(send_email_reminder(subject, body))
        except Exception:
            pass
        system_notify(subject, body)
