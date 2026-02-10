from datetime import datetime
from email.message import EmailMessage
import smtplib

from app.config import settings


def send_email_reminder(subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.email_to or not settings.email_from:
        return

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = settings.email_to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port or 587, timeout=20) as client:
        client.ehlo()
        try:
            client.starttls()
            client.ehlo()
        except smtplib.SMTPException:
            pass

        if settings.smtp_username and settings.smtp_password:
            client.login(settings.smtp_username, settings.smtp_password)

        client.send_message(message)


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
