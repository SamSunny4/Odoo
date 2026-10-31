"""Add indexes on issue_date and payment_date for Phase 8 finance dashboard

Revision ID: 006_phase8_reporting_indexes
Revises: 005_phase7_portal
Create Date: 2026-10-31 15:25:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_phase8_reporting_indexes'
down_revision = '005_phase7_portal'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_invoices_issue_date',
        'invoices',
        ['issue_date'],
        unique=False,
    )
    op.create_index(
        'ix_invoices_status_issue_date',
        'invoices',
        ['status', 'issue_date'],
        unique=False,
    )
    op.create_index(
        'ix_payments_payment_date',
        'payments',
        ['payment_date'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_payments_payment_date', table_name='payments')
    op.drop_index('ix_invoices_status_issue_date', table_name='invoices')
    op.drop_index('ix_invoices_issue_date', table_name='invoices')

