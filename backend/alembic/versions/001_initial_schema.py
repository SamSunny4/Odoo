"""Initial subscription management schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-31 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='customer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_role', 'users', ['role'])

    # 2. password_reset_tokens
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_password_reset_tokens_id', 'password_reset_tokens', ['id'])
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'])
    op.create_index('ix_password_reset_tokens_token', 'password_reset_tokens', ['token'], unique=True)

    # 3. customer_accounts
    op.create_table(
        'customer_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('billing_email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('tax_id', sa.String(length=50), nullable=True),
        sa.Column('billing_address_line1', sa.String(length=255), nullable=False),
        sa.Column('billing_address_line2', sa.String(length=255), nullable=True),
        sa.Column('billing_city', sa.String(length=100), nullable=False),
        sa.Column('billing_state', sa.String(length=100), nullable=True),
        sa.Column('billing_postal_code', sa.String(length=20), nullable=False),
        sa.Column('billing_country', sa.String(length=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_customer_accounts_id', 'customer_accounts', ['id'])
    op.create_index('ix_customer_accounts_billing_email', 'customer_accounts', ['billing_email'])

    # 4. customer_account_memberships
    op.create_table(
        'customer_account_memberships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('customer_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customer_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('membership_role', sa.String(length=20), nullable=False, server_default='owner'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('customer_account_id', 'user_id', name='uq_customer_account_user'),
    )
    op.create_index('ix_customer_account_memberships_id', 'customer_account_memberships', ['id'])
    op.create_index('ix_customer_account_memberships_customer_account_id', 'customer_account_memberships', ['customer_account_id'])
    op.create_index('ix_customer_account_memberships_user_id', 'customer_account_memberships', ['user_id'])

    # 5. products
    op.create_table(
        'products',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False, server_default='service'),
        sa.Column('sales_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('cost_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('sales_price >= 0', name='chk_product_sales_price_non_neg'),
        sa.CheckConstraint('cost_price >= 0', name='chk_product_cost_price_non_neg'),
    )
    op.create_index('ix_products_id', 'products', ['id'])
    op.create_index('ix_products_name', 'products', ['name'])

    # 6. product_variants
    op.create_table(
        'product_variants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('price_adjustment', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )
    op.create_index('ix_product_variants_id', 'product_variants', ['id'])
    op.create_index('ix_product_variants_product_id', 'product_variants', ['product_id'])

    # 7. plans
    op.create_table(
        'plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('cadence', sa.String(length=20), nullable=False, server_default='monthly'),
        sa.Column('base_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('min_quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('available_from', sa.Date(), nullable=True),
        sa.Column('available_to', sa.Date(), nullable=True),
        sa.Column('auto_close_on_expiry', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('allow_early_close', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('allow_pause', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('allow_renewal', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('base_price >= 0', name='chk_plan_base_price_non_neg'),
        sa.CheckConstraint('min_quantity >= 1', name='chk_plan_min_quantity_pos'),
    )
    op.create_index('ix_plans_id', 'plans', ['id'])
    op.create_index('ix_plans_name', 'plans', ['name'])

    # 8. tax_rules
    op.create_table(
        'tax_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('rate_percentage', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('name', name='uq_tax_rules_name'),
        sa.CheckConstraint('rate_percentage >= 0 AND rate_percentage <= 100', name='chk_tax_rate_range'),
    )
    op.create_index('ix_tax_rules_id', 'tax_rules', ['id'])

    # 9. discount_rules
    op.create_table(
        'discount_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('discount_type', sa.String(length=20), nullable=False),
        sa.Column('value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('scope', sa.String(length=20), nullable=False, server_default='subscription'),
        sa.Column('target_product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='SET NULL'), nullable=True),
        sa.Column('min_spend', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('min_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_usage_limit', sa.Integer(), nullable=True),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('value > 0', name='chk_discount_value_positive'),
        sa.CheckConstraint('min_spend >= 0', name='chk_discount_min_spend_non_neg'),
        sa.CheckConstraint('min_quantity >= 0', name='chk_discount_min_quantity_non_neg'),
    )
    op.create_index('ix_discount_rules_id', 'discount_rules', ['id'])

    # 10. quotation_templates
    op.create_table(
        'quotation_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('validity_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('default_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('plans.id', ondelete='SET NULL'), nullable=True),
        sa.Column('default_lines', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_quotation_templates_id', 'quotation_templates', ['id'])

    # 11. subscriptions
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('subscription_number', sa.String(length=50), nullable=False),
        sa.Column('customer_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customer_accounts.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('plans.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('next_billing_date', sa.Date(), nullable=True),
        sa.Column('billing_anchor_day', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('payment_terms_days', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('billing_anchor_day >= 1 AND billing_anchor_day <= 31', name='chk_sub_anchor_day_range'),
        sa.CheckConstraint('payment_terms_days >= 0', name='chk_sub_payment_terms_non_neg'),
    )
    op.create_index('ix_subscriptions_id', 'subscriptions', ['id'])
    op.create_index('ix_subscriptions_subscription_number', 'subscriptions', ['subscription_number'], unique=True)
    op.create_index('ix_subscriptions_customer_account_id', 'subscriptions', ['customer_account_id'])
    op.create_index('ix_subscriptions_plan_id', 'subscriptions', ['plan_id'])
    op.create_index('ix_subscriptions_status', 'subscriptions', ['status'])
    op.create_index('ix_subscriptions_next_billing_date', 'subscriptions', ['next_billing_date'])

    # 12. subscription_lines
    op.create_table(
        'subscription_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('product_variant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('product_variants.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('tax_rule_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_rules.id', ondelete='SET NULL'), nullable=True),
        sa.CheckConstraint('quantity >= 1', name='chk_sub_line_quantity_pos'),
        sa.CheckConstraint('unit_price >= 0', name='chk_sub_line_unit_price_non_neg'),
    )
    op.create_index('ix_subscription_lines_id', 'subscription_lines', ['id'])
    op.create_index('ix_subscription_lines_subscription_id', 'subscription_lines', ['subscription_id'])

    # 13. billing_runs
    op.create_table(
        'billing_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('run_date', sa.Date(), nullable=False),
        sa.Column('billing_period_start', sa.Date(), nullable=False),
        sa.Column('billing_period_end', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='preview'),
        sa.Column('total_evaluated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_amount_projected', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('committed_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('committed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_billing_runs_id', 'billing_runs', ['id'])
    op.create_index('ix_billing_runs_status', 'billing_runs', ['status'])

    # 14. billing_run_items
    op.create_table(
        'billing_run_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('billing_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('billing_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subscriptions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('expected_subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('expected_tax_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('expected_discount_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('expected_total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('prior_invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prior_invoice_total', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('variance_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('variance_reasons', sa.JSON(), nullable=False),
        sa.Column('warnings', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('skip_reason', sa.Text(), nullable=True),
        sa.Column('resulting_invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint('subscription_id', 'billing_run_id', name='uq_billing_run_subscription'),
    )
    op.create_index('ix_billing_run_items_id', 'billing_run_items', ['id'])
    op.create_index('ix_billing_run_items_billing_run_id', 'billing_run_items', ['billing_run_id'])
    op.create_index('ix_billing_run_items_subscription_id', 'billing_run_items', ['subscription_id'])

    # 15. invoices
    op.create_table(
        'invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('invoice_number', sa.String(length=50), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subscriptions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('customer_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customer_accounts.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('billing_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('billing_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('idempotency_key', sa.String(length=120), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('billing_period_start', sa.Date(), nullable=False),
        sa.Column('billing_period_end', sa.Date(), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('discount_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('paid_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('send_status', sa.String(length=20), nullable=False, server_default='not_sent'),
        sa.Column('customer_snapshot', sa.JSON(), nullable=False),
        sa.Column('billing_address_snapshot', sa.JSON(), nullable=False),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('paid_amount >= 0', name='chk_invoice_paid_amount_non_neg'),
        sa.CheckConstraint('total_amount >= 0', name='chk_invoice_total_amount_non_neg'),
    )
    op.create_index('ix_invoices_id', 'invoices', ['id'])
    op.create_index('ix_invoices_invoice_number', 'invoices', ['invoice_number'], unique=True)
    op.create_index('ix_invoices_subscription_id', 'invoices', ['subscription_id'])
    op.create_index('ix_invoices_customer_account_id', 'invoices', ['customer_account_id'])
    op.create_index('ix_invoices_idempotency_key', 'invoices', ['idempotency_key'], unique=True)
    op.create_index('ix_invoices_status', 'invoices', ['status'])
    op.create_index('ix_invoices_due_date', 'invoices', ['due_date'])

    # 16. invoice_lines
    op.create_table(
        'invoice_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('product_name_snapshot', sa.String(length=255), nullable=False),
        sa.Column('variant_name_snapshot', sa.String(length=255), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price_snapshot', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('tax_rule_name_snapshot', sa.String(length=100), nullable=True),
        sa.Column('tax_rate_snapshot', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.00'),
        sa.Column('tax_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('discount_rule_name_snapshot', sa.String(length=100), nullable=True),
        sa.Column('discount_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('line_total', sa.Numeric(precision=12, scale=2), nullable=False),
    )
    op.create_index('ix_invoice_lines_id', 'invoice_lines', ['id'])
    op.create_index('ix_invoice_lines_invoice_id', 'invoice_lines', ['invoice_id'])

    # 17. discount_redemptions
    op.create_table(
        'discount_redemptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('discount_rule_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('discount_rules.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('redeemed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('discount_rule_id', 'invoice_id', name='uq_discount_rule_invoice'),
    )
    op.create_index('ix_discount_redemptions_id', 'discount_redemptions', ['id'])
    op.create_index('ix_discount_redemptions_discount_rule_id', 'discount_redemptions', ['discount_rule_id'])
    op.create_index('ix_discount_redemptions_invoice_id', 'discount_redemptions', ['invoice_id'])
    op.create_index('ix_discount_redemptions_subscription_id', 'discount_redemptions', ['subscription_id'])

    # 18. payments
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('invoices.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('payment_method', sa.String(length=30), nullable=False, server_default='bank_transfer'),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('reference_note', sa.Text(), nullable=True),
        sa.Column('recorded_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('is_reversed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('amount > 0', name='chk_payment_amount_positive'),
    )
    op.create_index('ix_payments_id', 'payments', ['id'])
    op.create_index('ix_payments_invoice_id', 'payments', ['invoice_id'])

    # 19. payment_reversals
    op.create_table(
        'payment_reversals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payments.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reversal_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('reversed_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('payment_id', name='uq_payment_reversals_payment_id'),
        sa.CheckConstraint('reversal_amount > 0', name='chk_reversal_amount_positive'),
    )
    op.create_index('ix_payment_reversals_id', 'payment_reversals', ['id'])
    op.create_index('ix_payment_reversals_payment_id', 'payment_reversals', ['payment_id'])

    # 20. audit_events
    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('changes_json', sa.JSON(), nullable=False),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_audit_events_id', 'audit_events', ['id'])
    op.create_index('ix_audit_events_entity_type', 'audit_events', ['entity_type'])
    op.create_index('ix_audit_events_entity_id', 'audit_events', ['entity_id'])
    op.create_index('ix_audit_events_timestamp', 'audit_events', ['timestamp'])


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('payment_reversals')
    op.drop_table('payments')
    op.drop_table('discount_redemptions')
    op.drop_table('invoice_lines')
    op.drop_table('invoices')
    op.drop_table('billing_run_items')
    op.drop_table('billing_runs')
    op.drop_table('subscription_lines')
    op.drop_table('subscriptions')
    op.drop_table('quotation_templates')
    op.drop_table('discount_rules')
    op.drop_table('tax_rules')
    op.drop_table('plans')
    op.drop_table('product_variants')
    op.drop_table('products')
    op.drop_table('customer_account_memberships')
    op.drop_table('customer_accounts')
    op.drop_table('password_reset_tokens')
    op.drop_table('users')

