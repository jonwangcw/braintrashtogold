import pytest

pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from app.scheduling import notifications


def test_send_email_reminder_uses_smtp(monkeypatch):
    sent = {"called": False}

    class FakeSMTP:
        def __init__(self, host, port, timeout=20):
            assert host == "smtp.example.com"
            assert port == 587

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            return None

        def starttls(self):
            return None

        def login(self, username, password):
            assert username == "user"
            assert password == "pass"

        def send_message(self, message):
            sent["called"] = True
            assert message["Subject"] == "Subject"

    monkeypatch.setattr(notifications.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(notifications.settings, "smtp_port", 587)
    monkeypatch.setattr(notifications.settings, "smtp_username", "user")
    monkeypatch.setattr(notifications.settings, "smtp_password", "pass")
    monkeypatch.setattr(notifications.settings, "email_from", "from@example.com")
    monkeypatch.setattr(notifications.settings, "email_to", "to@example.com")
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)

    notifications.send_email_reminder("Subject", "Body")

    assert sent["called"] is True
