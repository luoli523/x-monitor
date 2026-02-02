"""Application configuration using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # X/Twitter API
    x_bearer_token: str

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Email SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_to: str = ""

    # Schedule
    summary_cron_hour: int = 8
    summary_cron_minute: int = 0

    # Database
    database_path: str = "data/x_monitor.db"

    @property
    def telegram_enabled(self) -> bool:
        """Check if Telegram notifications are configured."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def email_enabled(self) -> bool:
        """Check if email notifications are configured."""
        return bool(self.smtp_user and self.smtp_password and self.email_to)


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
