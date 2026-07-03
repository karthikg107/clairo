"""
Referral model (CLR-044).

One row per referred user (referred_user_id is UNIQUE — you can only be
referred once). The row is pending until the referred user completes
their first analysis, at which point both sides earn 1 bonus analysis
(the referrer capped at MAX_REFERRAL_BONUSES earned bonuses).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

MAX_REFERRAL_BONUSES = 10


class Referral(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "referrals"

    referrer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    referred_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # True only if the REFERRER received their bonus for this row (they may
    # already be at MAX_REFERRAL_BONUSES; the referred user's own bonus is
    # unconditional on completion).
    bonus_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<Referral referrer={self.referrer_user_id} "
            f"referred={self.referred_user_id} completed={self.completed_at is not None}>"
        )
