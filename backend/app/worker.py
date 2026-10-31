import smtplib
from datetime import date, timedelta
from email.message import EmailMessage
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus, SendStatus
from app.models.customer import CustomerAccount

# Initialize Celery app with Redis broker and result backend
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

# Synchronous engine for background Celery worker tasks
sync_engine = create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True)


@celery_app.task(name="tasks.send_invoice_email", bind=True, max_retries=3)
def send_invoice_email(self, invoice_id: str, recipient_email: str):
    """
    Background email delivery:
    Connects to SMTP host (Mailpit in local/dev) and sends customer invoice notification.
    """
    with Session(sync_engine) as session:
        inv = session.get(Invoice, invoice_id)
        if not inv:
            print(f"[Worker] Invoice {invoice_id} not found for email dispatch.")
            return {"status": "not_found"}

        msg = EmailMessage()
        msg["Subject"] = f"Invoice {inv.invoice_number} from Brightloop Software"
        msg["From"] = settings.SMTP_FROM
        msg["To"] = recipient_email

        body = f"""Dear Customer,

Your recurring subscription invoice {inv.invoice_number} for period {inv.billing_period_start} - {inv.billing_period_end} is ready.

Total Amount: ${inv.total_amount:.2f} {inv.currency}
Due Date: {inv.due_date}

You can view and manage your account anytime on your customer portal.

Thank you,
Brightloop Software Operations Team
"""
        msg.set_content(body)

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.send_message(msg)
            inv.send_status = SendStatus.SENT
            session.commit()
            print(f"[Worker] Successfully delivered invoice {inv.invoice_number} to {recipient_email} via SMTP.")
            return {"status": "sent", "invoice_number": inv.invoice_number}
        except Exception as exc:
            print(f"[Worker] SMTP delivery to {recipient_email} failed: {exc}")
            inv.send_status = SendStatus.FAILED
            session.commit()
            # Retry with exponential backoff if Celery is running
            raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="tasks.generate_recurring_invoices")
def generate_recurring_invoices():
    """
    Automated recurring billing job:
    Discovers all active subscriptions due today, creates invoices, and queues email dispatch.
    """
    today = date.today()
    print(f"[Worker] Executing scheduled recurring billing run for {today}...")

    with Session(sync_engine) as session:
        query = (
            select(Subscription)
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.next_billing_date <= today,
            )
        )
        due_subs = session.execute(query).scalars().all()
        invoices_created = 0

        for sub in due_subs:
            # Check idempotency
            idempotency_key = f"sub_{sub.id}_{today.isoformat()}"
            existing = session.execute(
                select(Invoice).where(Invoice.idempotency_key == idempotency_key)
            ).scalar_one_or_none()

            if existing:
                continue

            inv_number = f"INV-{today.year}-{str(invoices_created + 200).zfill(5)}"
            invoice = Invoice(
                invoice_number=inv_number,
                subscription_id=sub.id,
                customer_account_id=sub.customer_account_id,
                idempotency_key=idempotency_key,
                currency="USD",
                status=InvoiceStatus.CONFIRMED,
                billing_period_start=today.replace(day=1),
                billing_period_end=today,
                subtotal=sub.plan.base_price if sub.plan else 100,
                tax_amount=0,
                discount_amount=0,
                total_amount=sub.plan.base_price if sub.plan else 100,
                paid_amount=0,
                issue_date=today,
                due_date=today + timedelta(days=sub.payment_terms_days),
                send_status=SendStatus.NOT_SENT,
                customer_snapshot={"name": "Customer"},
                billing_address_snapshot={"address": "Standard"},
            )
            session.add(invoice)
            session.flush()

            # Advance billing date
            sub.next_billing_date = today + timedelta(days=30)
            invoices_created += 1

            # Dispatch email task asynchronously
            if sub.customer_account and sub.customer_account.billing_email:
                send_invoice_email.delay(str(invoice.id), sub.customer_account.billing_email)

        session.commit()
        print(f"[Worker] Completed automated run: {invoices_created} invoices generated.")
        return {"status": "completed", "invoices_created": invoices_created}


@celery_app.task(name="tasks.check_overdue_invoices")
def check_overdue_invoices():
    """
    Scheduled job: identifies overdue invoices and logs collection alerts.
    """
    today = date.today()
    with Session(sync_engine) as session:
        query = select(Invoice).where(
            Invoice.status == InvoiceStatus.CONFIRMED,
            Invoice.due_date < today,
            Invoice.paid_amount < Invoice.total_amount,
        )
        overdue_invoices = session.execute(query).scalars().all()
        print(f"[Worker] Overdue check complete: {len(overdue_invoices)} overdue invoices identified.")
        return {"overdue_count": len(overdue_invoices)}


# Periodic Celery Beat Schedule
celery_app.conf.beat_schedule = {
    "daily-recurring-billing-run": {
        "task": "tasks.generate_recurring_invoices",
        "schedule": crontab(hour=0, minute=5),
    },
    "hourly-overdue-check": {
        "task": "tasks.check_overdue_invoices",
        "schedule": crontab(minute=0),
    },
}
