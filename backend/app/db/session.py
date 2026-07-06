"""Async SQLAlchemy engine and session factory."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.logging import get_logger
from app.core.secrets import get_secret

logger = get_logger(__name__)

_engine = None
_session_factory = None


def _get_db_url() -> str:
    secret = get_secret("clairo/database")
    url = secret.get("url", "")
    if not url:
        raise RuntimeError("Database URL not found in secrets")
    # Ensure async driver prefix
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            _get_db_url(),
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # reconnect on stale connections
            # Security hardening item 10: cap every query at 10s server-side
            # (Postgres statement_timeout, in ms) so a slow/pathological query
            # can't tie up a connection indefinitely. asyncpg applies
            # server_settings as connection GUCs.
            connect_args={"server_settings": {"statement_timeout": "10000"}},
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
