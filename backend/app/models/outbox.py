import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, utc_now


class OutboxMessageStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"


class OutboxMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Transactional outbox for durable dispatch of emails, notifications, and integration events.
    Ensures message persistence within the business transaction before asynchronous delivery.
    """
    __tablename__ = "outbox_messages"

    topic: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OutboxMessageStatus.PENDING.value,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

