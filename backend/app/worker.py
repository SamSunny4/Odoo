import asyncio
import smtplib
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from email.message import EmailMessage

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import case, create_engine, func, select, delete, update, or_
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.clock import organization_today
from app.core.crypto import decrypt_secret
from app.models.billing_run import BillingRunItem, BillingRunItemStatus
from app.models.invoice import Invoice, InvoiceStatus, SendStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan
from app.models.user import User, UserRole
from app.models.customer import CustomerAccount
from app.models.outbox import OutboxMessage, OutboxMessageStatus
from app.services.billing import create_billing_preview, commit_billing_preview
from app.services.audit import record_audit_event
from app.services.email_templates import (
    invoice_email,
    overdue_reminder_email,
    overdue_reminder_window,
    password_reset_email,
    renewal_reminder_email,
)

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
    beat_schedule={
        "generate-recurring-invoices-daily": {
            "task": "tasks.generate_recurring_invoices",
            "schedule": crontab(hour=0, minute=0),
        },
        "check-overdue-invoices-hourly": {
            "task": "tasks.check_overdue_invoices",
            "schedule": crontab(minute=0),
        },
        "sync-outbox-messages-minute": {
            "task": "tasks.sync_outbox_messages",
            "schedule": crontab(minute="*"),
        },
    },
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


async def _close_expired_subscriptions(
    session: AsyncSession,
    *,
    today: date,
    actor_user_id: uuid.UUID,
) -> int:
    """Apply plan auto-close policy to active subscriptions past their expiry date."""
    expired = (await session.execute(
        select(Subscription)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.status.in_([SubscriptionStatus.CONFIRMED, SubscriptionStatus.ACTIVE, SubscriptionStatus.PAUSED]),
            Subscription.expiry_date.is_not(None),
            Subscription.expiry_date < today,
            or_(
                Subscription.cancel_at_period_end.is_(True),
                Plan.auto_close_on_expiry.is_(True),
            ),
        )
        .with_for_update(skip_locked=True)
    )).scalars().all()

    for subscription in expired:
        previous_status = subscription.status
        subscription.status = SubscriptionStatus.CLOSED
        await record_audit_event(
            session,
            entity_type="subscription",
            entity_id=subscription.id,
            action="AUTO_CLOSE_ON_EXPIRY",
            actor_user_id=actor_user_id,
            changes={
                "subscription_number": subscription.subscription_number,
                "status": {"from": previous_status.value, "to": SubscriptionStatus.CLOSED.value},
                "expiry_date": subscription.expiry_date.isoformat(),
            },
        )
    if expired:
        await session.commit()
    return len(expired)


async def _run_due_billing(batch_size: int = 250) -> tuple[int, int, int, int]:
    """Bill due subscriptions in bounded database transactions in the background worker."""
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
            auto_closed_count = await _close_expired_subscriptions(
                session,
                today=today,
                actor_user_id=admin.id,
            )
            due_subscription_ids = (await session.execute(
                select(Subscription.id)
                .where(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    func.coalesce(Subscription.next_billing_date, Subscription.start_date) <= today,
                )
                .order_by(
                    func.coalesce(Subscription.next_billing_date, Subscription.start_date),
                    Subscription.subscription_number,
                )
            )).scalars().all()
            if not due_subscription_ids:
                return 0, 0, auto_closed_count, 0

            invoices_created = 0
            emails_queued = 0
            failed_count = 0
            for offset in range(0, len(due_subscription_ids), batch_size):
                batch_ids = due_subscription_ids[offset:offset + batch_size]
                run, rows = await create_billing_preview(
                    session,
                    actor_user_id=admin.id,
                    as_of=today,
                    batch_limit=batch_size,
                    subscription_ids=batch_ids,
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
                invoices_created += len(invoices)
                emails_queued += sum(
                    1 for invoice in invoices
                    if invoice.customer_snapshot.get("billing_email")
                )
                failed_count += await session.scalar(
                    select(func.count(BillingRunItem.id)).where(
                        BillingRunItem.billing_run_id == run.id,
                        BillingRunItem.status == BillingRunItemStatus.FAILED,
                    )
                ) or 0
            return invoices_created, emails_queued, auto_closed_count, failed_count
    finally:
        await async_engine.dispose()


@celery_app.task(name="tasks.generate_recurring_invoices")
def generate_recurring_invoices():
    """Automatically bill due clean subscriptions through the shared billing engine."""
    invoices_created, emails_queued, auto_closed_count, failed_count = asyncio.run(_run_due_billing())
    return {
        "status": "completed",
        "invoices_created": invoices_created,
        "emails_queued": emails_queued,
        "subscriptions_auto_closed": auto_closed_count,
        "failed_count": failed_count,
    }


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
        to_email = msg.payload.get("to") or msg.payload.get("recipient_email")
        subject = msg.payload.get("subject", "Notification from Brightloop")
        body = msg.payload.get("body")

        if msg.payload.get("type") == "invoice_issued" and not body:
            subject, body = invoice_email(
                invoice_number=msg.payload.get("invoice_number", ""),
                amount=msg.payload.get("total_amount", "0.00"),
                currency=msg.payload.get("currency", ""),
                due_date=msg.payload.get("due_date", "see customer portal"),
            )

        # Handle password reset with encrypted token
        if msg.payload.get("type") == "password_reset" and "encrypted_reset_token" in msg.payload:
            raw_token = decrypt_secret(msg.payload["encrypted_reset_token"])
            frontend_base = settings.FRONTEND_URL.rstrip('/')
            reset_link = f"{frontend_base}/reset-password?token={raw_token}"
            subject, body = password_reset_email(reset_link)

        if not to_email or not body:
            raise ValueError(f"Outbox email message {msg.id} missing required 'to' or 'body' field.")

        email_msg = EmailMessage()
        email_msg["Subject"] = subject
        email_msg["From"] = settings.SMTP_FROM
        email_msg["To"] = to_email
        email_msg.set_content(body)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.send_message(email_msg)


def _enrich_invoice_email_payload(session: Session, msg: OutboxMessage) -> None:
    if msg.payload.get("type") != "invoice_issued" or not msg.payload.get("invoice_id"):
        return
    invoice = session.get(Invoice, uuid.UUID(str(msg.payload["invoice_id"])))
    if not invoice:
        return
    msg.payload.setdefault("invoice_number", invoice.invoice_number)
    msg.payload.setdefault("total_amount", str(invoice.total_amount))
    msg.payload.setdefault("due_date", invoice.due_date.isoformat())
    msg.payload.setdefault("currency", invoice.currency)


async def _async_enrich_invoice_email_payload(session: AsyncSession, msg: OutboxMessage) -> None:
    if msg.payload.get("type") != "invoice_issued" or not msg.payload.get("invoice_id"):
        return
    invoice = await session.get(Invoice, uuid.UUID(str(msg.payload["invoice_id"])))
    if not invoice:
        return
    msg.payload.setdefault("invoice_number", invoice.invoice_number)
    msg.payload.setdefault("total_amount", str(invoice.total_amount))
    msg.payload.setdefault("due_date", invoice.due_date.isoformat())
    msg.payload.setdefault("currency", invoice.currency)


def _sync_invoice_delivery_state(session: Session, msg: OutboxMessage, *, delivered: bool) -> None:
    if msg.payload.get("type") != "invoice_issued" or not msg.payload.get("invoice_id"):
        return
    invoice = session.get(Invoice, uuid.UUID(str(msg.payload["invoice_id"])))
    if not invoice:
        return
    if delivered:
        invoice.send_status = SendStatus.SENT
        invoice.sent_at = msg.sent_at or datetime.now(timezone.utc)
    elif msg.status == OutboxMessageStatus.FAILED.value:
        invoice.send_status = SendStatus.FAILED


async def _async_invoice_delivery_state(session: AsyncSession, msg: OutboxMessage, *, delivered: bool) -> None:
    if msg.payload.get("type") != "invoice_issued" or not msg.payload.get("invoice_id"):
        return
    invoice = await session.get(Invoice, uuid.UUID(str(msg.payload["invoice_id"])))
    if not invoice:
        return
    if delivered:
        invoice.send_status = SendStatus.SENT
        invoice.sent_at = msg.sent_at or datetime.now(timezone.utc)
    elif msg.status == OutboxMessageStatus.FAILED.value:
        invoice.send_status = SendStatus.FAILED


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
            await _async_enrich_invoice_email_payload(session, msg)
            await asyncio.to_thread(_deliver_outbox_message, msg)
            msg.status = OutboxMessageStatus.SENT.value
            msg.sent_at = datetime.now(timezone.utc)
            msg.last_error = None
            await _async_invoice_delivery_state(session, msg, delivered=True)
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
            await _async_invoice_delivery_state(session, msg, delivered=False)
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
            _enrich_invoice_email_payload(session, msg)
            _deliver_outbox_message(msg)
            msg.status = OutboxMessageStatus.SENT.value
            msg.sent_at = datetime.now(timezone.utc)
            msg.last_error = None
            _sync_invoice_delivery_state(session, msg, delivered=True)
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
            _sync_invoice_delivery_state(session, msg, delivered=False)
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
                OutboxMessage.status == OutboxMessageStatus.SENT.value,
                OutboxMessage.created_at < cutoff,
            )
        )
        session.commit()
        return {"purged_records": result.rowcount}


@celery_app.task(name="tasks.queue_billing_reminders")
def queue_billing_reminders():
    """Queue idempotent one-week and one-day renewal reminders plus weekly overdue reminders."""
    today = organization_today()
    renewal_cutoff = today + timedelta(days=7)
    queued_renewals = 0
    queued_overdue = 0

    with Session(sync_engine) as session:
        due_subscriptions = session.execute(
            select(Subscription, CustomerAccount, Plan)
            .join(CustomerAccount, CustomerAccount.id == Subscription.customer_account_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                func.coalesce(Subscription.next_billing_date, Subscription.start_date).between(today, renewal_cutoff),
            )
        ).all()
        for subscription, account, plan in due_subscriptions:
            billing_date = subscription.next_billing_date or subscription.start_date
            days_until_billing = (billing_date - today).days
            reminder_window = "week" if days_until_billing > 1 else "final"
            dedupe_key = f"renewal-reminder:{subscription.id}:{billing_date.isoformat()}:{reminder_window}"
            if session.execute(select(OutboxMessage.id).where(OutboxMessage.dedupe_key == dedupe_key)).scalar_one_or_none():
                continue
            subject, body = renewal_reminder_email(
                company_name=account.company_name,
                plan_name=plan.name,
                subscription_number=subscription.subscription_number,
                billing_date=billing_date,
                lead_days=days_until_billing,
            )
            session.add(OutboxMessage(
                topic="email",
                dedupe_key=dedupe_key,
                payload={
                    "type": "renewal_reminder",
                    "to": account.billing_email,
                    "subject": subject,
                    "body": body,
                },
                status=OutboxMessageStatus.PENDING.value,
                retry_count=0,
                max_retries=3,
                scheduled_at=datetime.now(timezone.utc),
            ))
            queued_renewals += 1

        overdue_invoices = session.execute(
            select(Invoice).where(
                Invoice.status == InvoiceStatus.CONFIRMED,
                Invoice.due_date < today,
                Invoice.paid_amount < Invoice.total_amount,
            )
        ).scalars().all()
        for invoice in overdue_invoices:
            days_overdue = (today - invoice.due_date).days
            if days_overdue < 1:
                continue
            reminder_window = overdue_reminder_window(days_overdue)
            recipient = (invoice.customer_snapshot or {}).get("billing_email")
            if not recipient:
                continue
            dedupe_key = f"overdue-reminder:{invoice.id}:{reminder_window}"
            if session.execute(select(OutboxMessage.id).where(OutboxMessage.dedupe_key == dedupe_key)).scalar_one_or_none():
                continue
            balance = max(Decimal("0.00"), Decimal(str(invoice.total_amount)) - Decimal(str(invoice.paid_amount)))
            subject, body = overdue_reminder_email(
                invoice_number=invoice.invoice_number,
                due_date=invoice.due_date,
                balance=balance,
                currency=invoice.currency,
            )
            session.add(OutboxMessage(
                topic="email",
                dedupe_key=dedupe_key,
                payload={
                    "type": "overdue_reminder",
                    "to": recipient,
                    "subject": subject,
                    "body": body,
                },
                status=OutboxMessageStatus.PENDING.value,
                retry_count=0,
                max_retries=3,
                scheduled_at=datetime.now(timezone.utc),
            ))
            queued_overdue += 1

        session.commit()

    return {"renewal_reminders_queued": queued_renewals, "overdue_reminders_queued": queued_overdue}


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
    "daily-billing-reminders": {
        "task": "tasks.queue_billing_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    "daily-outbox-cleanup": {
        "task": "tasks.cleanup_outbox_messages",
        "schedule": crontab(hour=3, minute=0),
    },
}
