import uuid
from typing import Any, Dict, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.outbox import OutboxMessage, OutboxMessageStatus
from app.models.base import utc_now


async def create_outbox_message(
    db: AsyncSession,
    *,
    topic: str,
    payload: Dict[str, Any],
    scheduled_at: Optional[datetime] = None,
    max_retries: int = 3,
    dedupe_key: Optional[str] = None,
) -> OutboxMessage:
    """
    Persist an outbound message in the transactional outbox.
    Ensures message durability within the same database transaction as business mutations.
    """
    if dedupe_key:
        existing = (await db.execute(
            select(OutboxMessage).where(OutboxMessage.dedupe_key == dedupe_key)
        )).scalar_one_or_none()
        if existing:
            return existing

    message = OutboxMessage(
        topic=topic,
        payload=payload,
        dedupe_key=dedupe_key,
        status=OutboxMessageStatus.PENDING.value,
        retry_count=0,
        max_retries=max_retries,
        scheduled_at=scheduled_at or utc_now(),
    )
    db.add(message)
    return message

