"""Track quotation validity separately from subscription expiry.

Revision ID: 004_quote_validity
Revises: 003_outbox_messages
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_quote_validity"
down_revision: Union[str, None] = "003_outbox_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("quote_valid_until", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "quote_valid_until")
