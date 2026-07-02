"""
User model.

SECURITY:
- deleted_at enables GDPR hard-delete (see gdpr_delete_user())
- No document content stored here or anywhere in schema
- tos_accepted_at is immutable once set (write via record_tos_acceptance only)
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Increment this when TOS/Privacy Policy changes materially.
# Users who accepted an older version will be shown the screen again.
CURRENT_TOS_VERSION = "1.0"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    # Clerk auth ID — source of truth for identity
    clerk_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)

    # TOS / Privacy Policy acceptance (CLR-022)
    # Null = never accepted; populated on first acceptance.
    # Version bumps when legal copy changes — triggers re-acceptance.
    tos_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tos_version: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )

    # Soft-delete timestamp — actual hard delete done by gdpr_delete_user()
    # Row stays briefly for audit trail, then purged by nightly job
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Lifetime free-tier analysis count (CLR-025) — 2 free analyses per user,
    # not a rolling window. See app/services/quota.py.
    free_analyses_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    analyses: Mapped[list["Analysis"]] = relationship(  # noqa: F821
        "Analysis", back_populates="user", cascade="all, delete-orphan"
    )
    subscription: Mapped["Subscription | None"] = relationship(  # noqa: F821
        "Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def has_accepted_current_tos(self) -> bool:
        return (
            self.tos_accepted_at is not None
            and self.tos_version == CURRENT_TOS_VERSION
        )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
