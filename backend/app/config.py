from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration with sane defaults for the MVP."""

    database_url: str = "sqlite:///./app.db"
    timezone: str = "Asia/Kolkata"
    reminder_start_hour: int = 9
    reminder_end_hour: int = 18

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    return Settings()
