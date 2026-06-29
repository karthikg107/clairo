"""
User model.

SECURITY:
- deleted_at enables GDPR hard-delete (see gdpr_delete_user())
- No document content stored here or anywhere in schema
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    # Clerk auth ID — source of truth for identity
    clerk_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)

    # Soft-delete timestamp — actual hard delete done by gdpr_delete_user()
    # Row stays briefly for audit trail, then purged by nightly job
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
