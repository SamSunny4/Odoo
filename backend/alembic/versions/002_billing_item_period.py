"""Persist billing periods on Control Tower preview items.

Revision ID: 002_billing_item_period
Revises: 001_initial_schema
"""
from alembic import op
import sqlalchemy as sa


revision = "002_billing_item_period"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "billing_run_items",
        sa.Column("billing_period_start", sa.Date(), nullable=True),
    )
    op.add_column(
        "billing_run_items",
        sa.Column("billing_period_end", sa.Date(), nullable=True),
    )
    op.execute(
        "UPDATE billing_run_items SET billing_period_start = CURRENT_DATE, "
        "billing_period_end = CURRENT_DATE WHERE billing_period_start IS NULL OR billing_period_end IS NULL"
    )
    op.alter_column("billing_run_items", "billing_period_start", nullable=False)
    op.alter_column("billing_run_items", "billing_period_end", nullable=False)


def downgrade() -> None:
    op.drop_column("billing_run_items", "billing_period_end")
    op.drop_column("billing_run_items", "billing_period_start")
