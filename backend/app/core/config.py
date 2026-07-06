"""Application settings via pydantic-settings."""
import os
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_cors_origins() -> list[str]:
    """Production origins + localhost, plus any comma-separated EXTRA_CORS_ORIGINS
    (e.g. a Vercel preview/production URL when clairo.app isn't the host yet)."""
    base = ["https://clairo.app", "https://www.clairo.app", "http://localhost:3000"]
    extra = os.getenv("EXTRA_CORS_ORIGINS", "")
    return base + [o.strip() for o in extra.split(",") if o.strip()]


def _default_allowed_hosts() -> list[str]:
    """Production hosts + localhost, plus any comma-separated EXTRA_ALLOWED_HOSTS
    (e.g. a *.onrender.com host when clairo.app's own domain isn't wired up yet)."""
    base = ["clairo.app", "*.clairo.app", "localhost"]
    extra = os.getenv("EXTRA_ALLOWED_HOSTS", "")
    return base + [h.strip() for h in extra.split(",") if h.strip()]


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

    # CORS — clairo.app + localhost, plus any EXTRA_CORS_ORIGINS (local dev)
    cors_origins: list[str] = Field(default_factory=_default_cors_origins)

    # Frontend base URL — used to build Stripe Checkout success/cancel redirects (CLR-026)
    frontend_base_url: str = "http://localhost:3000"

    # Security
    allowed_hosts: list[str] = Field(default_factory=_default_allowed_hosts)

    # File validation — ClamAV requires a running clamd daemon, which some
    # free/managed hosts (e.g. Render's free tier) have no way to run
    # alongside the app. Defaults to enabled everywhere; set
    # VIRUS_SCAN_ENABLED=false only where no clamd is reachable. Magic-byte
    # and MIME-allowlist checks still run regardless of this flag.
    virus_scan_enabled: bool = True

    # Clerk authentication
    # JWKS URL: https://clerk.com/docs/backend-requests/handling/manual-jwt
    clerk_jwks_url: str = "https://api.clerk.dev/v1/jwks"
    clerk_issuer: str = ""  # e.g. https://<your-clerk-domain>.clerk.accounts.dev

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
