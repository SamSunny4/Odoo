"""Allow multiple immutable partial reversals for one payment.

Revision ID: 007_phase6_payment_reversals
Revises: 006_phase8_reporting_indexes
Create Date: 2026-10-31 16:30:00
"""

from alembic import op


revision = "007_phase6_payment_reversals"
down_revision = "006_phase8_reporting_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_payment_reversals_payment_id",
        "payment_reversals",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_payment_reversals_payment_id",
        "payment_reversals",
        ["payment_id"],
    )
