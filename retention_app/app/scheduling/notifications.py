from datetime import datetime
from email.message import EmailMessage
import smtplib

from app.config import settings


def send_email_reminder(subject: str, body: str) -> None:
    if not settings.enable_email_reminders:
        return
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
    print(f"[DEBUG] system_notify: title={title!r}")
    # plyer's NOTIFYICONDATAW caps szInfoTitle at 64 and szInfo at 256
    plyer_title = title[:63]
    plyer_message = message[:255]
    try:
        from plyer import notification

        notification.notify(title=plyer_title, message=plyer_message, timeout=10)
        print("[DEBUG] system_notify: plyer succeeded")
        return
    except Exception as exc:
        print(f"[DEBUG] system_notify: plyer failed ({exc}); trying PowerShell fallback")

    import subprocess
    import sys

    if sys.platform != "win32":
        return
    safe_title = title.replace("'", "''")
    safe_msg = message.replace("'", "''")
    ps_script = (
        "[reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null; "
        "[reflection.assembly]::loadwithpartialname('System.Drawing') | Out-Null; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $true; "
        f"$n.ShowBalloonTip(8000, '{safe_title}', '{safe_msg}', "
        "[System.Windows.Forms.ToolTipIcon]::None); "
        "Start-Sleep -Seconds 9; "
        "$n.Dispose()"
    )
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        print("[DEBUG] system_notify: PowerShell fallback launched")
    except Exception as exc2:
        print(f"[DEBUG] system_notify: PowerShell fallback also failed ({exc2})")


def reminder_body(content_title: str, url: str) -> str:
    return f"Quiz due for {content_title}. Open {url}"


def reminder_subject(content_title: str) -> str:
    return f"Quiz due: {content_title}"


def reminder_time() -> datetime:
    return datetime.utcnow()
