"""Subscription model — Stripe billing state."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SubscriptionTier(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    canceled = "canceled"
    past_due = "past_due"
    trialing = "trialing"
    unpaid = "unpaid"


class Subscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, name="subscription_tier_enum"),
        nullable=False,
        default=SubscriptionTier.free,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status_enum"),
        nullable=False,
        default=SubscriptionStatus.active,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscription")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Subscription user_id={self.user_id} tier={self.tier} status={self.status}>"
