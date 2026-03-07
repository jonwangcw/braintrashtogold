from datetime import datetime, timedelta, timezone

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


_DEDUP_WINDOW_HOURS = 12


class ReminderScheduler:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.scheduler = BackgroundScheduler(timezone=settings.timezone)

    def start(self) -> None:
        self.scheduler.add_job(self.check_due_items, "interval", minutes=5)
        # DEBUG: one-shot job to verify toast delivery; bypasses DB due-items check
        debug_run_at = datetime.now(tz=timezone.utc) + timedelta(seconds=30)
        self.scheduler.add_job(self._debug_notify, "date", run_date=debug_run_at, id="debug_notify")
        self.scheduler.start()

    def _debug_notify(self) -> None:
        print("[DEBUG] _debug_notify: firing test notification")
        system_notify("Retention App", "Debug: notification system is working")
        print("[DEBUG] _debug_notify: system_notify returned")

    def shutdown(self) -> None:
        self.scheduler.shutdown()

    def check_due_items(self) -> None:
        with self.session_factory() as session:
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
                recent = (
                    session.query(models.Notification)
                    .filter(
                        models.Notification.content_id == state.content_id,
                        models.Notification.kind == models.NotificationKind.system,
                        models.Notification.status == models.NotificationStatus.sent,
                        models.Notification.sent_at >= cutoff,
                    )
                    .first()
                )
                if recent:
                    continue
                self._send_notifications(session, state)

    def _send_notifications(self, session: Session, state: models.ScheduleState) -> None:
        content = session.get(models.Content, state.content_id)
        if not content:
            return

        now = datetime.utcnow()
        url = f"{settings.app_base_url}/content/{content.id}"
        subject = reminder_subject(content.title)
        body = reminder_body(content.title, url)

        email_notification: models.Notification | None = None
        if settings.enable_email_reminders:
            email_notification = models.Notification(
                content_id=content.id,
                kind=models.NotificationKind.email,
                scheduled_for=now,
                status=models.NotificationStatus.pending,
            )
            session.add(email_notification)

        system_notification = models.Notification(
            content_id=content.id,
            kind=models.NotificationKind.system,
            scheduled_for=now,
            status=models.NotificationStatus.pending,
        )
        session.add(system_notification)
        session.commit()

        if email_notification is not None:
            try:
                send_email_reminder(subject, body)
                email_notification.status = models.NotificationStatus.sent
                email_notification.sent_at = datetime.utcnow()
                email_notification.error = None
            except Exception as exc:  # noqa: BLE001
                email_notification.status = models.NotificationStatus.failed
                email_notification.error = str(exc)

        try:
            system_notify(subject, body)
            system_notification.status = models.NotificationStatus.sent
            system_notification.sent_at = datetime.utcnow()
            system_notification.error = None
        except Exception as exc:  # noqa: BLE001
            system_notification.status = models.NotificationStatus.failed
            system_notification.error = str(exc)

        if email_notification is not None:
            session.add(email_notification)
        session.add(system_notification)
        session.commit()
