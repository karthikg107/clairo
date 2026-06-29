"""
Audit log model — append-only security event log.

SECURITY:
- The app DB user has INSERT only on this table — no UPDATE or DELETE
- This is enforced in the migration via REVOKE/GRANT SQL
- metadata_json must NEVER contain document content
"""
import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from sqlalchemy import DateTime, func


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_log"

    # created_at only — no updated_at (immutable)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Safe metadata only — action outcome, IDs, error codes
    # NEVER log document content, PII beyond user_id, or raw file bytes
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action!r} user_id={self.user_id}>"
