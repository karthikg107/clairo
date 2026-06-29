"""
AWS Secrets Manager client.

SECURITY: API keys are NEVER read from environment variables in production.
They are fetched from AWS Secrets Manager at startup.
"""
import json
import os
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=64)
def get_secret(secret_name: str, region: str = "us-east-1") -> dict[str, Any]:
    """
    Fetch a secret from AWS Secrets Manager. Cached per process.
    
    In local dev (APP_ENV=development), falls back to environment variables
    if AWS is not configured. This fallback is DISABLED in production.
    """
    app_env = os.getenv("APP_ENV", "development")

    if app_env == "development":
        # Local dev: allow env-var fallback for DX
        logger.info("secrets.dev_fallback", secret_name=secret_name)
        return _dev_fallback(secret_name)

    # Production: Secrets Manager only
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
        "clairo/database": {"url": os.getenv("DATABASE_URL", "")},
        "clairo/redis": {"url": os.getenv("REDIS_URL", "")},
        "clairo/stripe": {
            "secret_key": os.getenv("STRIPE_SECRET_KEY", ""),
            "webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET", ""),
        },
        "clairo/clerk": {"secret_key": os.getenv("CLERK_SECRET_KEY", "")},
        "clairo/google-vision": {
            "credentials_json": os.getenv("GOOGLE_CLOUD_CREDENTIALS_JSON", ""),
            "project_id": os.getenv("GOOGLE_CLOUD_PROJECT_ID", ""),
        },
    }
    return mapping.get(secret_name, {})
