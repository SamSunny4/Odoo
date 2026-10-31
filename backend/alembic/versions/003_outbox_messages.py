"""Create outbox_messages table

Revision ID: 003_outbox_messages
Revises: 002_billing_item_period
Create Date: 2026-10-31 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '003_outbox_messages'
down_revision: Union[str, None] = '002_billing_item_period'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'outbox_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('topic', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default=sa.text('3')),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_outbox_messages_id', 'outbox_messages', ['id'])
    op.create_index('ix_outbox_messages_topic', 'outbox_messages', ['topic'])
    op.create_index('ix_outbox_messages_status', 'outbox_messages', ['status'])
    op.create_index('ix_outbox_messages_scheduled_at', 'outbox_messages', ['scheduled_at'])


def downgrade() -> None:
    op.drop_table('outbox_messages')

