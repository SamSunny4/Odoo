import pytest
from decimal import Decimal
from datetime import date
from sqlalchemy import select

from app.models.audit import AuditEvent
from app.models.outbox import OutboxMessage
from app.models.user import User, UserRole
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus, SendStatus
from tests.conftest import auth_cookies


@pytest.mark.asyncio
async def test_audit_event_written_on_signup_and_staff_creation(client, db_session, seed_users):
    """Sign-up and admin staff creation write AuditEvent entries."""
    admin = seed_users["admin"]

    # 1. Customer Signup
    signup_payload = {
        "email": "brandnew.customer@company.com",
        "password": "CustomerSecure#2026",
        "full_name": "New Customer",
        "company_name": "New Horizons LLC",
        "billing_address_line1": "456 Enterprise Way",
        "billing_city": "Denver",
        "billing_postal_code": "80202",
        "billing_country": "US",
    }
    signup_res = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_res.status_code == 201

    events_signup = (
        await db_session.execute(
            select(AuditEvent).where(AuditEvent.action == "SIGNUP")
        )
    ).scalars().all()
    assert len(events_signup) == 1
    assert events_signup[0].entity_type == "user"
    assert events_signup[0].changes_json["email"] == "brandnew.customer@company.com"

    # 2. Admin Creates Staff
    client.cookies.clear()
    client.cookies.update(auth_cookies(admin))

    staff_payload = {
        "email": "clara.staff@brightloop.local",
        "password": "ClaraStaff#2026!",
        "full_name": "Clara Oswald",
        "role": "staff",
    }
    staff_res = await client.post("/api/v1/admin/staff", json=staff_payload)
    assert staff_res.status_code == 201

    events_staff = (
        await db_session.execute(
            select(AuditEvent).where(AuditEvent.action == "CREATE_STAFF")
        )
    ).scalars().all()
    assert len(events_staff) == 1
    assert events_staff[0].entity_type == "user"
    assert events_staff[0].actor_user_id == admin.id
    assert events_staff[0].changes_json["role"] == "staff"


@pytest.mark.asyncio
async def test_audit_event_on_subscription_pause_and_resume(client, db_session, seed_users):
    """Pausing and resuming subscriptions write AuditEvent entries."""
    staff = seed_users["staff"]
    plan = seed_users["plan"]
    account = seed_users["account_a"]

    # Plan permits pause
    plan.allow_pause = True
    sub = Subscription(
        subscription_number="SUB-AUDIT-001",
        customer_account_id=account.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2026, 1, 1),
        billing_anchor_day=1,
        payment_terms_days=15,
    )
    db_session.add(sub)
    await db_session.commit()

    client.cookies.update(auth_cookies(staff))

    # Pause
    res_pause = await client.post(f"/api/v1/subscriptions/{sub.id}/pause")
    assert res_pause.status_code == 200

    pause_event = (
        await db_session.execute(
            select(AuditEvent).where(
                AuditEvent.entity_type == "subscription",
                AuditEvent.entity_id == sub.id,
                AuditEvent.action == "PAUSE",
            )
        )
    ).scalar_one_or_none()
    assert pause_event is not None
    assert pause_event.actor_user_id == staff.id

    # Resume
    res_resume = await client.post(f"/api/v1/subscriptions/{sub.id}/resume")
    assert res_resume.status_code == 200

    resume_event = (
        await db_session.execute(
            select(AuditEvent).where(
                AuditEvent.entity_type == "subscription",
                AuditEvent.entity_id == sub.id,
                AuditEvent.action == "RESUME",
            )
        )
    ).scalar_one_or_none()
    assert resume_event is not None
    assert resume_event.actor_user_id == staff.id


@pytest.mark.asyncio
async def test_audit_event_on_invoice_confirm_and_payment(client, db_session, seed_users):
    """Confirming draft invoices and recording payments write AuditEvent entries."""
    staff = seed_users["staff"]
    account = seed_users["account_a"]
    plan = seed_users["plan"]

    sub = Subscription(
        subscription_number="SUB-AUDIT-INV-999",
        customer_account_id=account.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2026, 3, 1),
        billing_anchor_day=1,
        payment_terms_days=15,
    )
    db_session.add(sub)
    await db_session.flush()

    inv = Invoice(
        invoice_number="INV-AUDIT-999",
        subscription_id=sub.id,
        customer_account_id=account.id,
        idempotency_key="idemp_inv_audit_999",
        customer_snapshot={"company_name": "Acme Corp"},
        billing_address_snapshot={"city": "Austin"},
        currency="INR",
        status=InvoiceStatus.DRAFT,
        billing_period_start=date(2026, 3, 1),
        billing_period_end=date(2026, 3, 31),
        subtotal=Decimal("150.00"),
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("150.00"),
        paid_amount=Decimal("0.00"),
        issue_date=date(2026, 3, 1),
        due_date=date(2026, 3, 16),
        send_status=SendStatus.NOT_SENT,
    )
    db_session.add(inv)
    await db_session.commit()

    client.cookies.update(auth_cookies(staff))

    # 1. Confirm Draft Invoice
    res_confirm = await client.post(f"/api/v1/invoices/{inv.id}/confirm")
    assert res_confirm.status_code == 200

    inv_event = (
        await db_session.execute(
            select(AuditEvent).where(
                AuditEvent.entity_type == "invoice",
                AuditEvent.entity_id == inv.id,
                AuditEvent.action == "CONFIRM",
            )
        )
    ).scalar_one_or_none()
    assert inv_event is not None

    # 2. Record Payment
    payment_payload = {
        "invoice_id": str(inv.id),
        "amount": 150.00,
        "payment_method": "credit_card",
        "payment_date": "2026-03-05",
        "reference_note": "Paid in full via Stripe card terminal",
    }
    res_pay = await client.post("/api/v1/payments", json=payment_payload)
    assert res_pay.status_code == 201

    pay_event = (
        await db_session.execute(
            select(AuditEvent).where(AuditEvent.action == "CREATE_PAYMENT")
        )
    ).scalar_one_or_none()
    assert pay_event is not None
    assert pay_event.changes_json["amount"] == "150.0"

