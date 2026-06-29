"""Application settings via pydantic-settings."""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Clairo API"
    app_version: str = "0.1.0"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # AWS
    aws_region: str = "us-east-1"
    aws_secret_prefix: str = "clairo"  # e.g. clairo/anthropic

    # CORS — clairo.app and localhost only
    cors_origins: list[str] = Field(
        default=["https://clairo.app", "https://www.clairo.app", "http://localhost:3000"]
    )

    # Security
    allowed_hosts: list[str] = Field(default=["clairo.app", "*.clairo.app", "localhost"])

    # Sentry
    sentry_dsn: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
