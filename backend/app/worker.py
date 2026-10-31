import asyncio
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import case, create_engine, func, select, delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.clock import organization_today
from app.core.crypto import decrypt_secret
from app.models.billing_run import BillingRunItemStatus
from app.models.invoice import Invoice, InvoiceStatus, SendStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User, UserRole
from app.models.outbox import OutboxMessage, OutboxMessageStatus
from app.services.billing import create_billing_preview, commit_billing_preview

celery_app = Celery(
    "brightloop_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.ORGANIZATION_TIMEZONE,
    enable_utc=True,
)

sync_engine = create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True)


@celery_app.task(name="tasks.send_invoice_email", bind=True, max_retries=3)
def send_invoice_email(self, invoice_id: str, recipient_email: str):
    """Send a committed invoice notice and retain delivery status for retry."""
    with Session(sync_engine) as session:
        invoice = session.get(Invoice, uuid.UUID(invoice_id))
        if not invoice:
            return {"status": "not_found"}

        message = EmailMessage()
        message["Subject"] = f"Invoice {invoice.invoice_number} from Brightloop Software"
        message["From"] = settings.SMTP_FROM
        message["To"] = recipient_email
        message.set_content(
            f"Your invoice {invoice.invoice_number} for "
            f"{invoice.billing_period_start} through {invoice.billing_period_end} is ready.\n\n"
            f"Amount: {invoice.total_amount} {invoice.currency}\n"
            f"Due date: {invoice.due_date}\n\n"
            "Sign in to the Brightloop customer portal to view your invoice."
        )

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.send_message(message)
            invoice.send_status = SendStatus.SENT
            session.commit()
            return {"status": "sent", "invoice_number": invoice.invoice_number}
        except Exception as exc:
            invoice.send_status = SendStatus.FAILED
            session.commit()
            raise self.retry(exc=exc, countdown=60)


async def _run_due_billing() -> tuple[int, list[tuple[str, str]]]:
    """Create and commit a preview using the same calculation path as the admin UI."""
    async_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            admin = (await session.execute(
                select(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True)).limit(1)
            )).scalar_one_or_none()
            if not admin:
                raise RuntimeError("Recurring billing requires an active seeded admin account.")

            today = organization_today()
            due_count = await session.scalar(
                select(func.count(Subscription.id)).where(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    func.coalesce(Subscription.next_billing_date, Subscription.start_date) <= today,
                )
            )
            if not due_count:
                return 0, []
            run, rows = await create_billing_preview(
                session,
                actor_user_id=admin.id,
                as_of=today,
            )
            clean_item_ids = [
                row.item.id for row in rows
                if row.item.status == BillingRunItemStatus.PENDING
            ]
            _, invoices = await commit_billing_preview(
                session,
                billing_run_id=run.id,
                approved_item_ids=clean_item_ids,
                actor_user_id=admin.id,
                as_of=today,
                allow_empty=True,
            )
            deliveries = [
                (str(invoice.id), str(invoice.customer_snapshot.get("billing_email", "")))
                for invoice in invoices
                if invoice.customer_snapshot.get("billing_email")
            ]
            return len(invoices), deliveries
    finally:
        await async_engine.dispose()


@celery_app.task(name="tasks.generate_recurring_invoices")
def generate_recurring_invoices():
    """Automatically bill due clean subscriptions through the shared billing engine."""
    invoices_created, deliveries = asyncio.run(_run_due_billing())
    for invoice_id, recipient in deliveries:
        send_invoice_email.delay(invoice_id, recipient)
    return {"status": "completed", "invoices_created": invoices_created, "emails_queued": len(deliveries)}


@celery_app.task(name="tasks.check_overdue_invoices")
def check_overdue_invoices():
    """Count unpaid, overdue invoices for the operations queue."""
    today = organization_today()
    with Session(sync_engine) as session:
        overdue = session.execute(
            select(Invoice.id).where(
                Invoice.status == InvoiceStatus.CONFIRMED,
                Invoice.due_date < today,
                Invoice.paid_amount < Invoice.total_amount,
            )
        ).all()
        return {"overdue_count": len(overdue)}


def _deliver_outbox_message(msg: OutboxMessage) -> None:
    """Helper delivering a single OutboxMessage via appropriate adapter."""
    if msg.topic == "email":
        to_email = msg.payload.get("to")
        subject = msg.payload.get("subject", "Notification from Brightloop")
        body = msg.payload.get("body")

        # Handle password reset with encrypted token
        if msg.payload.get("type") == "password_reset" and "encrypted_reset_token" in msg.payload:
            raw_token = decrypt_secret(msg.payload["encrypted_reset_token"])
            frontend_base = settings.FRONTEND_URL.rstrip('/')
            reset_link = f"{frontend_base}/reset-password?token={raw_token}"
            subject = msg.payload.get("subject", "Password Reset Request — Brightloop Software")
            body = (
                f"Hello,\n\n"
                f"A password reset request was initiated for your Brightloop account.\n\n"
                f"Use the following secure link within 1 hour to reset your password:\n"
                f"{reset_link}\n\n"
                f"If you did not request this, please disregard this email.\n\n"
                f"Brightloop Security Team"
            )

        if not to_email or not body:
            raise ValueError(f"Outbox email message {msg.id} missing required 'to' or 'body' field.")

        email_msg = EmailMessage()
        email_msg["Subject"] = subject
        email_msg["From"] = settings.SMTP_FROM
        email_msg["To"] = to_email
        email_msg.set_content(body)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.send_message(email_msg)


def _stuck_outbox_ids_query(stuck_cutoff: datetime):
    return (
        select(OutboxMessage.id)
        .where(
            OutboxMessage.status == OutboxMessageStatus.PROCESSING.value,
            OutboxMessage.updated_at < stuck_cutoff,
        )
        .order_by(OutboxMessage.updated_at.asc())
        .with_for_update(skip_locked=True)
    )


def _reclaim_stuck_outbox_statement(stuck_ids: list, stuck_cutoff: datetime, now: datetime):
    next_retry_count = OutboxMessage.retry_count + 1
    return (
        update(OutboxMessage)
        .where(
            OutboxMessage.id.in_(stuck_ids),
            OutboxMessage.status == OutboxMessageStatus.PROCESSING.value,
            OutboxMessage.updated_at < stuck_cutoff,
        )
        .values(
            retry_count=next_retry_count,
            status=case(
                (next_retry_count >= OutboxMessage.max_retries, OutboxMessageStatus.FAILED.value),
                else_=OutboxMessageStatus.PENDING.value,
            ),
            last_error="Worker crashed or timed out while processing; reclaimed.",
            scheduled_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )


def _pending_outbox_ids_query(now: datetime, batch_size: int):
    return (
        select(OutboxMessage.id)
        .where(
            OutboxMessage.status == OutboxMessageStatus.PENDING.value,
            OutboxMessage.scheduled_at <= now,
        )
        .order_by(OutboxMessage.created_at.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )


def _claim_outbox_message_statement(message_id, now: datetime):
    # Conditional update is a compare-and-set fallback on databases that ignore FOR UPDATE.
    return (
        update(OutboxMessage)
        .where(
            OutboxMessage.id == message_id,
            OutboxMessage.status == OutboxMessageStatus.PENDING.value,
            OutboxMessage.scheduled_at <= now,
        )
        .values(status=OutboxMessageStatus.PROCESSING.value, updated_at=now)
        .execution_options(synchronize_session=False)
    )


async def _claim_pending_outbox_messages_async(
    session: AsyncSession,
    now: datetime,
    batch_size: int,
) -> list[OutboxMessage]:
    candidate_ids = (await session.execute(_pending_outbox_ids_query(now, batch_size))).scalars().all()
    claimed_ids = []
    for message_id in candidate_ids:
        result = await session.execute(_claim_outbox_message_statement(message_id, now))
        if result.rowcount == 1:
            claimed_ids.append(message_id)

    # Commit claims before any external I/O so other workers skip these rows.
    await session.commit()
    if not claimed_ids:
        return []

    result = await session.execute(
        select(OutboxMessage)
        .where(OutboxMessage.id.in_(claimed_ids))
        .order_by(OutboxMessage.created_at.asc())
        .execution_options(populate_existing=True)
    )
    return result.scalars().all()


def _claim_pending_outbox_messages_sync(
    session: Session,
    now: datetime,
    batch_size: int,
) -> list[OutboxMessage]:
    candidate_ids = session.execute(_pending_outbox_ids_query(now, batch_size)).scalars().all()
    claimed_ids = []
    for message_id in candidate_ids:
        result = session.execute(_claim_outbox_message_statement(message_id, now))
        if result.rowcount == 1:
            claimed_ids.append(message_id)

    # Commit claims before any external I/O so other workers skip these rows.
    session.commit()
    if not claimed_ids:
        return []

    result = session.execute(
        select(OutboxMessage)
        .where(OutboxMessage.id.in_(claimed_ids))
        .order_by(OutboxMessage.created_at.asc())
        .execution_options(populate_existing=True)
    )
    return result.scalars().all()


async def process_outbox_messages_async(
    session: AsyncSession,
    batch_size: int = 50,
    stuck_timeout_minutes: int = 5,
) -> dict:
    """
    Async outbox dispatcher:
    1. Reclaims messages stuck in PROCESSING due to worker crashes.
    2. Pulls pending messages due for delivery.
    3. Securely decrypts encrypted payload secrets (e.g. password reset tokens) and sends via SMTP.
    4. Records delivery status and handles retries with exponential backoff.
    """
    now = datetime.now(timezone.utc)

    # Step 1: Reclaim crashed workers with locked selection and conditional updates.
    stuck_cutoff = now - timedelta(minutes=stuck_timeout_minutes)
    stuck_ids = (await session.execute(_stuck_outbox_ids_query(stuck_cutoff))).scalars().all()
    reclaimed_count = 0
    if stuck_ids:
        reclaimed = await session.execute(_reclaim_stuck_outbox_statement(stuck_ids, stuck_cutoff, now))
        reclaimed_count = max(reclaimed.rowcount or 0, 0)
        await session.commit()

    # Step 2: Atomically claim pending messages before sending them.
    messages = await _claim_pending_outbox_messages_async(session, now, batch_size)

    processed_count = 0
    for msg in messages:
        try:
            await asyncio.to_thread(_deliver_outbox_message, msg)
            msg.status = OutboxMessageStatus.SENT.value
            msg.sent_at = datetime.now(timezone.utc)
            msg.last_error = None
            await session.commit()
            processed_count += 1
        except Exception as exc:
            msg.retry_count += 1
            msg.last_error = str(exc)
            if msg.retry_count >= msg.max_retries:
                msg.status = OutboxMessageStatus.FAILED.value
            else:
                msg.status = OutboxMessageStatus.PENDING.value
                msg.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=30 * (2 ** msg.retry_count))
            await session.commit()

    return {"processed": processed_count, "reclaimed": reclaimed_count, "batch_size": len(messages)}


def _process_outbox_sync(session: Session, batch_size: int = 50, stuck_timeout_minutes: int = 5) -> dict:
    """Synchronous dispatcher implementation for Celery tasks."""
    now = datetime.now(timezone.utc)

    # Step 1: Reclaim crashed workers with locked selection and conditional updates.
    stuck_cutoff = now - timedelta(minutes=stuck_timeout_minutes)
    stuck_ids = session.execute(_stuck_outbox_ids_query(stuck_cutoff)).scalars().all()
    reclaimed_count = 0
    if stuck_ids:
        reclaimed = session.execute(_reclaim_stuck_outbox_statement(stuck_ids, stuck_cutoff, now))
        reclaimed_count = max(reclaimed.rowcount or 0, 0)
        session.commit()

    # Step 2: Atomically claim pending messages before sending them.
    messages = _claim_pending_outbox_messages_sync(session, now, batch_size)

    processed_count = 0
    for msg in messages:
        try:
            _deliver_outbox_message(msg)
            msg.status = OutboxMessageStatus.SENT.value
            msg.sent_at = datetime.now(timezone.utc)
            msg.last_error = None
            session.commit()
            processed_count += 1
        except Exception as exc:
            msg.retry_count += 1
            msg.last_error = str(exc)
            if msg.retry_count >= msg.max_retries:
                msg.status = OutboxMessageStatus.FAILED.value
            else:
                msg.status = OutboxMessageStatus.PENDING.value
                msg.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=30 * (2 ** msg.retry_count))
            session.commit()

    return {"processed": processed_count, "reclaimed": reclaimed_count, "batch_size": len(messages)}


@celery_app.task(name="tasks.process_outbox_messages")
def process_outbox_messages(batch_size: int = 50, stuck_timeout_minutes: int = 5):
    """Celery scheduled task wrapping synchronous outbox processing."""
    with Session(sync_engine) as session:
        return _process_outbox_sync(session, batch_size, stuck_timeout_minutes)


@celery_app.task(name="tasks.cleanup_outbox_messages")
def cleanup_outbox_messages(retention_days: int = 14):
    """
    Purges old sent and failed outbox messages past retention window to conserve database space.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)
    with Session(sync_engine) as session:
        result = session.execute(
            delete(OutboxMessage).where(
                OutboxMessage.status.in_([OutboxMessageStatus.SENT.value, OutboxMessageStatus.FAILED.value]),
                OutboxMessage.created_at < cutoff,
            )
        )
        session.commit()
        return {"purged_records": result.rowcount}


celery_app.conf.beat_schedule = {
    "daily-recurring-billing-run": {
        "task": "tasks.generate_recurring_invoices",
        "schedule": crontab(hour=0, minute=5),
    },
    "hourly-overdue-check": {
        "task": "tasks.check_overdue_invoices",
        "schedule": crontab(minute=0),
    },
    "outbox-dispatch-every-minute": {
        "task": "tasks.process_outbox_messages",
        "schedule": 60.0,
    },
    "daily-outbox-cleanup": {
        "task": "tasks.cleanup_outbox_messages",
        "schedule": crontab(hour=3, minute=0),
    },
}
