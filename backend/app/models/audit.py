import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, utc_now


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """
    Immutable audit log capturing critical mutations
    (pricing changes, role assignments, plan policy edits, cancellations).
    """
    __tablename__ = "audit_events"

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "CREATE", "UPDATE", "STATUS_CHANGE", "CANCEL"
    changes_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

