from datetime import datetime, timedelta

from app.db.engine import Base, engine, SessionLocal
from app.db import models
from app.scheduling.scheduler import ReminderScheduler


def test_scheduler_skips_email_notifications_when_disabled(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        content = models.Content(
            title="Item",
            content_type=models.ContentType.webpage,
            source_url="https://example.com",
            status=models.ContentStatus.ready,
        )
        session.add(content)
        session.commit()
        session.refresh(content)

        state = models.ScheduleState(
            content_id=content.id,
            step_index=0,
            next_due_at=datetime.utcnow() - timedelta(minutes=1),
            is_terminated=False,
        )
        session.add(state)
        session.commit()

    monkeypatch.setattr("app.scheduling.scheduler.settings.enable_email_reminders", False)

    scheduler = ReminderScheduler(SessionLocal)
    scheduler.check_due_items()

    with SessionLocal() as session:
        notifications = session.query(models.Notification).all()

    assert all(n.kind != models.NotificationKind.email for n in notifications)
