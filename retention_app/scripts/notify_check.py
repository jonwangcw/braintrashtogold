"""Standalone quiz reminder — intended to be run by Windows Task Scheduler.

Run directly to test:
    .venv\\Scripts\\python.exe scripts\\notify_check.py
"""
import os
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent   # scripts/
_app_root = _here.parent                  # retention_app/
os.chdir(_app_root)                       # sqlite:///./app.db resolves relative to here
sys.path.insert(0, str(_app_root))

from datetime import datetime, timedelta  # noqa: E402

from app.config import settings           # noqa: E402
from app.db.engine import SessionLocal    # noqa: E402
from app.db import models                 # noqa: E402
from app.scheduling.notifications import (  # noqa: E402
    reminder_body,
    reminder_subject,
    system_notify,
)

_DEDUP_WINDOW_HOURS = 12


def main() -> None:
    if not settings.enable_system_notifications:
        return

    with SessionLocal() as session:
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=_DEDUP_WINDOW_HOURS)

        due_items = (
            session.query(models.ScheduleState)
            .join(models.Content)
            .filter(models.ScheduleState.is_terminated.is_(False))
            .filter(models.ScheduleState.next_due_at <= now)
            .all()
        )

        for state in due_items:
            content = session.get(models.Content, state.content_id)
            if not content:
                continue

            recent = (
                session.query(models.Notification)
                .filter(
                    models.Notification.content_id == content.id,
                    models.Notification.kind == models.NotificationKind.system,
                    models.Notification.status == models.NotificationStatus.sent,
                    models.Notification.sent_at >= cutoff,
                )
                .first()
            )
            if recent:
                continue

            notif = models.Notification(
                content_id=content.id,
                kind=models.NotificationKind.system,
                scheduled_for=now,
                status=models.NotificationStatus.pending,
            )
            session.add(notif)
            session.commit()

            try:
                url = f"{settings.app_base_url}/content/{content.id}"
                system_notify(reminder_subject(content.title), reminder_body(content.title, url))
                notif.status = models.NotificationStatus.sent
                notif.sent_at = datetime.utcnow()
                notif.error = None
            except Exception as exc:
                notif.status = models.NotificationStatus.failed
                notif.error = str(exc)

            session.add(notif)
            session.commit()


if __name__ == "__main__":
    main()
