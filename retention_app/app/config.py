from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL")

    whisper_model: str = Field(default="base", alias="WHISPER_MODEL")

    enable_email_reminders: bool = Field(default=False, alias="ENABLE_EMAIL_REMINDERS")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int | None = Field(default=None, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    email_from: str | None = Field(default=None, alias="EMAIL_FROM")
    email_to: str | None = Field(default=None, alias="EMAIL_TO")

    enable_system_notifications: bool = Field(default=False, alias="ENABLE_SYSTEM_NOTIFICATIONS")
    app_base_url: str = Field(default="http://localhost:8000", alias="APP_BASE_URL")
    timezone: str = Field(default="UTC", alias="TIMEZONE")
    enable_legacy_quizzes: bool = Field(default=True, alias="ENABLE_LEGACY_QUIZZES")


settings = Settings()
