"""Add self-service cancellation and idempotent communications outbox keys.

Revision ID: 005_phase7_portal
Revises: 004_quote_validity
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_phase7_portal"
down_revision: Union[str, None] = "004_quote_validity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("is_add_on", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "subscriptions",
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("outbox_messages", sa.Column("dedupe_key", sa.String(length=255), nullable=True))
    op.create_index("uq_outbox_messages_dedupe_key", "outbox_messages", ["dedupe_key"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_outbox_messages_dedupe_key", table_name="outbox_messages")
    op.drop_column("outbox_messages", "dedupe_key")
    op.drop_column("products", "is_add_on")
    op.drop_column("subscriptions", "cancel_at_period_end")
