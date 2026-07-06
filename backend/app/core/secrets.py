"""
Secrets resolution — pluggable backend.

SECURITY: on the "aws" backend (the default outside local dev), API keys
are NEVER read from environment variables — they are fetched from AWS
Secrets Manager at startup.

Backend selection (env var SECRETS_BACKEND):
  - "aws" (default when APP_ENV != development): AWS Secrets Manager only.
  - "env": resolve every secret from plain environment variables instead,
    via the same mapping used for local dev. This exists for deploying to
    a host with no AWS access (e.g. Render, Railway, Fly.io) — set
    SECRETS_BACKEND=env explicitly there. It is NEVER the default for a
    non-development APP_ENV, so a misconfigured production deployment
    fails loudly (missing AWS creds) rather than silently reading env
    vars it wasn't meant to.
  - APP_ENV=development always uses the env-var mapping regardless of
    SECRETS_BACKEND (unchanged local-dev behavior).
"""
import json
import os
from functools import lru_cache
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=64)
def get_secret(secret_name: str, region: str = "us-east-1") -> dict[str, Any]:
    """
    Fetch a secret. Cached per process. See module docstring for backend
    selection (AWS Secrets Manager vs. plain env vars).
    """
    app_env = os.getenv("APP_ENV", "development")
    backend = os.getenv("SECRETS_BACKEND", "aws")

    if app_env == "development" or backend == "env":
        logger.info("secrets.env_fallback", secret_name=secret_name, app_env=app_env)
        return _dev_fallback(secret_name)

    # AWS Secrets Manager — imported lazily so the "env" backend (e.g. a
    # Render deployment) never needs AWS credentials configured at all.
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client("secretsmanager", region_name=region)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        logger.info("secrets.fetched", secret_name=secret_name)
        raw = response.get("SecretString") or response.get("SecretBinary", "")
        return json.loads(raw) if isinstance(raw, str) else {}
    except ClientError as exc:
        logger.error("secrets.fetch_failed", secret_name=secret_name, error=str(exc))
        raise RuntimeError(f"Failed to fetch secret '{secret_name}'") from exc


def _dev_fallback(secret_name: str) -> dict[str, Any]:
    """Map secret names to local env var names for development only."""
    mapping: dict[str, dict[str, str]] = {
        "clairo/anthropic": {"api_key": os.getenv("ANTHROPIC_API_KEY", "")},
        # Local-dev only: used when LLM_PROVIDER=openai (see analysis.py).
        "clairo/openai": {"api_key": os.getenv("OPENAI_API_KEY", "")},
        "clairo/database": {"url": os.getenv("DATABASE_URL", "")},
        "clairo/redis": {"url": os.getenv("REDIS_URL", "")},
        "clairo/stripe": {
            "secret_key": os.getenv("STRIPE_SECRET_KEY", ""),
            "webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET", ""),
            # Price IDs are created once per Stripe account (Dashboard or
            # `stripe prices create`) and referenced here — never hardcoded.
            "price_starter_monthly": os.getenv("STRIPE_PRICE_STARTER_MONTHLY", ""),
            "price_starter_annual": os.getenv("STRIPE_PRICE_STARTER_ANNUAL", ""),
            "price_pro_monthly": os.getenv("STRIPE_PRICE_PRO_MONTHLY", ""),
            "price_pro_annual": os.getenv("STRIPE_PRICE_PRO_ANNUAL", ""),
            "price_team_monthly": os.getenv("STRIPE_PRICE_TEAM_MONTHLY", ""),
            "price_team_annual": os.getenv("STRIPE_PRICE_TEAM_ANNUAL", ""),
        },
        "clairo/clerk": {"secret_key": os.getenv("CLERK_SECRET_KEY", "")},
        "clairo/google-vision": {
            "credentials_json": os.getenv("GOOGLE_CLOUD_CREDENTIALS_JSON", ""),
            "project_id": os.getenv("GOOGLE_CLOUD_PROJECT_ID", ""),
        },
    }
    return mapping.get(secret_name, {})
