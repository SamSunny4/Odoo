"""Plain-text email templates shared by API actions and background workers."""

from datetime import date
from decimal import Decimal


def password_reset_email(reset_link: str) -> tuple[str, str]:
    return (
        "Password Reset Request — Brightloop Software",
        "\n".join([
            "Hello,",
            "",
            "A password reset request was initiated for your Brightloop account.",
            "",
            "Use this secure link within 1 hour to reset your password:",
            reset_link,
            "",
            "If you did not request this, please disregard this email.",
            "",
            "Brightloop Security Team",
        ]),
    )


def quotation_email(
    *, company_name: str, quote_number: str, plan_name: str, start_date: date,
    valid_until: date | None, lines: list[str], subtotal: Decimal, discount: Decimal,
    tax: Decimal, total: Decimal, currency: str,
) -> tuple[str, str]:
    body = "\n".join([
        f"Hello {company_name},",
        "",
        f"Your quotation {quote_number} is ready.",
        f"Plan: {plan_name}",
        f"Start date: {start_date}",
        f"Valid until: {valid_until or 'No expiry set'}",
        "",
        "Quoted lines:",
        *(lines or ["- No additional product lines"]),
        "",
        f"Subtotal: {subtotal} {currency}",
        f"Discount: {discount} {currency}",
        f"Tax: {tax} {currency}",
        f"Total: {total} {currency}",
        "",
        "Sign in to the Brightloop customer portal to review your offer.",
        "",
        "Brightloop Software",
    ])
    return f"Brightloop quotation {quote_number}", body


def invoice_email(*, invoice_number: str, amount: Decimal | str, currency: str, due_date: date | str) -> tuple[str, str]:
    return (
        f"Invoice {invoice_number} from Brightloop Software",
        "\n".join([
            f"Your invoice {invoice_number} is ready.",
            "",
            f"Amount: {amount} {currency}",
            f"Due date: {due_date}",
            "",
            "Sign in to the Brightloop customer portal to view and download your invoice.",
            "",
            "Brightloop Software",
        ]),
    )


def payment_receipt_email(
    *, company_name: str, invoice_number: str, amount: Decimal, currency: str,
    payment_method: str, payment_date: date, balance: Decimal,
) -> tuple[str, str]:
    return (
        f"Payment receipt for invoice {invoice_number}",
        "\n".join([
            f"Hello {company_name},",
            "",
            f"We received your payment for Brightloop invoice {invoice_number}.",
            "",
            f"Amount received: {amount} {currency}",
            f"Payment method: {payment_method.replace('_', ' ')}",
            f"Payment date: {payment_date}",
            f"Remaining balance: {balance} {currency}",
            "",
            "Thank you,",
            "Brightloop Software",
        ]),
    )


def renewal_reminder_email(
    *, company_name: str, plan_name: str, subscription_number: str,
    billing_date: date, lead_days: int,
) -> tuple[str, str]:
    return (
        f"Subscription {subscription_number} renews soon",
        "\n".join([
            f"Hello {company_name},",
            "",
            f"Your {plan_name} subscription {subscription_number} is scheduled to renew on {billing_date}.",
            f"This is a reminder {lead_days} day(s) ahead.",
            "",
            "Sign in to the Brightloop customer portal to review your subscription.",
            "",
            "Brightloop Software",
        ]),
    )


def overdue_reminder_email(*, invoice_number: str, due_date: date, balance: Decimal, currency: str) -> tuple[str, str]:
    return (
        f"Payment overdue: invoice {invoice_number}",
        "\n".join([
            f"Invoice {invoice_number} was due on {due_date}.",
            "",
            f"Outstanding balance: {balance} {currency}",
            "Please sign in to the Brightloop customer portal to review the invoice and arrange payment.",
            "",
            "If you have already paid, please disregard this reminder.",
            "",
            "Brightloop Software",
        ]),
    )


def portal_subscription_update_email(
    *, customer_name: str, action: str, subscription_number: str,
    effective_date: date, status: str,
) -> tuple[str, str]:
    return (
        f"Subscription {subscription_number} updated",
        "\n".join([
            f"Hello {customer_name},",
            "",
            f"Your request to {action.replace('_', ' ')} subscription {subscription_number} was applied.",
            f"Effective date: {effective_date}",
            f"Current status: {status}.",
            "",
            "Brightloop Software",
        ]),
    )
