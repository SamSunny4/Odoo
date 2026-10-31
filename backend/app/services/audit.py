import uuid
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditEvent


async def record_audit_event(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor_user_id: Optional[uuid.UUID] = None,
    changes: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """
    Append an immutable audit log entry for critical domain mutations
    (user creation, role changes, subscriptions, invoices, payments, policy edits).
    """
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_user_id=actor_user_id,
        changes_json=changes or {},
    )
    db.add(event)
    return event

