from datetime import datetime

import aiosmtplib
from email.message import EmailMessage

from app.config import settings


async def send_email_reminder(subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.email_to or not settings.email_from:
        return
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = settings.email_to
    message["Subject"] = subject
    message.set_content(body)
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port or 587,
        username=settings.smtp_username,
        password=settings.smtp_password,
        start_tls=True,
    )


def system_notify(title: str, message: str) -> None:
    if not settings.enable_system_notifications:
        return
    try:
        from plyer import notification

        notification.notify(title=title, message=message, timeout=10)
    except Exception:
        return


def reminder_body(content_title: str, url: str) -> str:
    return f"Quiz due for {content_title}. Open {url}"


def reminder_subject(content_title: str) -> str:
    return f"Quiz due: {content_title}"


def reminder_time() -> datetime:
    return datetime.utcnow()
