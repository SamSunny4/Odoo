import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import auth_cookies
from app.models.catalog import ProductType
from app.models.plan import BillingCadence
from app.models.discount import DiscountType, DiscountScope
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.audit import AuditEvent
from app.worker import _close_expired_subscriptions


@pytest.mark.asyncio
async def test_product_crud_and_cost_price_redaction(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    staff = seed_users["staff"]
    customer = seed_users["customer_a"]

    admin_cookies = auth_cookies(admin)
    staff_cookies = auth_cookies(staff)
    customer_cookies = auth_cookies(customer)

    invalid_variant_price = await client.post(
        "/api/v1/products",
        json={
            "name": "Invalid Variant Product",
            "type": "goods",
            "sales_price": "10.00",
            "cost_price": "5.00",
            "variants": [{"name": "Below Zero", "price_adjustment": "-11.00"}],
        },
        cookies=auth_cookies(admin),
    )
    assert invalid_variant_price.status_code == 422

    # 1. Non-admin forbidden to create product
    res = await client.post(
        "/api/v1/products",
        json={
            "name": "Custom Workstation",
            "type": "goods",
            "sales_price": "1200.00",
            "cost_price": "800.00",
            "notes": "Assembly details and components",
        },
        cookies=staff_cookies,
    )
    assert res.status_code == 403

    # 2. Admin creates product
    res = await client.post(
        "/api/v1/products",
        json={
            "name": "Custom Workstation",
            "type": "goods",
            "sales_price": "1200.00",
            "cost_price": "800.00",
            "notes": "Assembly details and components",
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 201
    prod_data = res.json()
    product_id = prod_data["id"]
    assert prod_data["name"] == "Custom Workstation"
    assert prod_data["sales_price"] == "1200.00"
    assert prod_data["cost_price"] == "800.00"

    # 3. Customer views product: cost_price is redacted (None)
    res = await client.get(f"/api/v1/products/{product_id}", cookies=customer_cookies)
    assert res.status_code == 200
    assert res.json()["cost_price"] is None

    # 4. Staff views product: cost_price is redacted
    res = await client.get(f"/api/v1/products/{product_id}", cookies=staff_cookies)
    assert res.status_code == 200
    assert res.json()["cost_price"] is None
    assert res.json()["notes"] == "Assembly details and components"

    # 5. Admin updates product (PUT and PATCH support)
    res = await client.put(
        f"/api/v1/products/{product_id}",
        json={"sales_price": "1350.00", "notes": "Updated assembly details"},
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["sales_price"] == "1350.00"

    # 6. Admin archives product
    res = await client.delete(f"/api/v1/products/{product_id}", cookies=admin_cookies)
    assert res.status_code == 200
    assert res.json()["is_active"] is False


@pytest.mark.asyncio
async def test_consumable_product_type_from_admin_catalog(client: AsyncClient, seed_users):
    admin_cookies = auth_cookies(seed_users["admin"])
    res = await client.post(
        "/api/v1/products",
        json={
            "name": "Provisioned Storage",
            "type": "consumable",
            "sales_price": "12.00",
            "cost_price": "4.00",
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 201
    assert res.json()["type"] == "consumable"


@pytest.mark.asyncio
async def test_product_variants_and_price_adjustments(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # 1. Add standard variant
    res = await client.post(
        f"/api/v1/products/{product.id}/variants",
        json={
            "name": "Standard Brand",
            "price_adjustment": "0.00",
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 201
    var1_id = res.json()["id"]
    assert res.json()["price_adjustment"] == "0.00"

    # 2. Add Odoo Brand variant with +560.00 price adjustment
    res = await client.post(
        f"/api/v1/products/{product.id}/variants",
        json={
            "name": "Odoo Brand Edition",
            "price_adjustment": "560.00",
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 201
    var2_id = res.json()["id"]
    assert res.json()["price_adjustment"] == "560.00"

    # 3. Update variant (PUT and PATCH support)
    res = await client.put(
        f"/api/v1/products/{product.id}/variants/{var2_id}",
        json={"price_adjustment": "575.50"},
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["price_adjustment"] == "575.50"

    # 4. List variants for product
    res = await client.get(f"/api/v1/products/{product.id}/variants", cookies=admin_cookies)
    assert res.status_code == 200
    variants = res.json()
    assert len(variants) == 2


@pytest.mark.asyncio
async def test_variant_price_floor_is_enforced_when_catalog_prices_change(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    variant = await client.post(
        f"/api/v1/products/{product.id}/variants",
        json={"name": "Discounted Edition", "price_adjustment": "-50.00"},
        cookies=admin_cookies,
    )
    assert variant.status_code == 201

    lower_base = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"sales_price": "40.00"},
        cookies=admin_cookies,
    )
    assert lower_base.status_code == 422

    archived = await client.delete(
        f"/api/v1/products/{product.id}/variants/{variant.json()['id']}",
        cookies=admin_cookies,
    )
    assert archived.status_code == 200
    preview = await client.post(
        "/api/v1/catalog/calculate-preview",
        json={
            "product_lines": [{
                "product_id": str(product.id),
                "variant_id": variant.json()["id"],
            }],
        },
        cookies=admin_cookies,
    )
    assert preview.status_code == 409


@pytest.mark.asyncio
async def test_plan_crud_and_cadence_policies(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    staff = seed_users["staff"]
    admin_cookies = auth_cookies(admin)
    staff_cookies = auth_cookies(staff)

    today = date.today()
    next_year = today + timedelta(days=365)

    # 1. Staff forbidden to create plan
    res = await client.post(
        "/api/v1/plans",
        json={
            "name": "Enterprise Annual",
            "cadence": "yearly",
            "base_price": "2400.00",
            "min_quantity": 5,
        },
        cookies=staff_cookies,
    )
    assert res.status_code == 403

    # 2. Incompatible policy validation: neither allows renewal nor enables auto-close upon expiry
    res = await client.post(
        "/api/v1/plans",
        json={
            "name": "Invalid Policy Plan",
            "cadence": "monthly",
            "base_price": "150.00",
            "allow_renewal": False,
            "auto_close_on_expiry": False,
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 422

    # 3. Admin creates valid plan with cadence and policies
    res = await client.post(
        "/api/v1/plans",
        json={
            "name": "Enterprise Annual",
            "cadence": "yearly",
            "base_price": "2400.00",
            "min_quantity": 5,
            "available_from": today.isoformat(),
            "available_to": next_year.isoformat(),
            "allow_pause": True,
            "allow_early_close": True,
            "auto_close_on_expiry": True,
            "allow_renewal": True,
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 201
    plan_data = res.json()
    plan_id = plan_data["id"]
    assert plan_data["cadence"] == "yearly"
    assert plan_data["min_quantity"] == 5
    assert plan_data["allow_pause"] is True
    assert plan_data["allow_early_close"] is True

    # 4. Admin updates plan
    res = await client.put(
        f"/api/v1/plans/{plan_id}",
        json={"base_price": "2600.00", "min_quantity": 10},
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["base_price"] == "2600.00"
    assert res.json()["min_quantity"] == 10

    # 5. Admin archives plan
    res = await client.delete(f"/api/v1/plans/{plan_id}", cookies=admin_cookies)
    assert res.status_code == 200
    assert res.json()["is_active"] is False


@pytest.mark.asyncio
async def test_plan_policy_only_updates_persist_and_validate_merged_state(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    plan = seed_users["plan"]
    admin_cookies = auth_cookies(admin)
    today = date.today()
    next_month = today + timedelta(days=30)

    # Policy-only PATCH must persist even when there are no name/price changes.
    res = await client.patch(
        f"/api/v1/plans/{plan.id}",
        json={
            "available_to": next_month.isoformat(),
            "allow_pause": False,
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["available_to"] == next_month.isoformat()
    assert res.json()["allow_pause"] is False

    # A partial update must be checked against the existing date range.
    res = await client.patch(
        f"/api/v1/plans/{plan.id}",
        json={"available_from": (next_month + timedelta(days=1)).isoformat()},
        cookies=admin_cookies,
    )
    assert res.status_code == 422

    # Explicit null clears an optional availability boundary.
    res = await client.patch(
        f"/api/v1/plans/{plan.id}",
        json={"available_to": None},
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["available_to"] is None


@pytest.mark.asyncio
async def test_expired_auto_close_plan_subscriptions_are_closed_and_audited(db_session, seed_users):
    admin = seed_users["admin"]
    account = seed_users["account_a"]
    plan = seed_users["plan"]
    plan.auto_close_on_expiry = True
    db_session.add_all([
        Subscription(
            subscription_number="SUB-AUTO-CLOSE-1",
            customer_account_id=account.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            start_date=date.today() - timedelta(days=60),
            expiry_date=date.today() - timedelta(days=1),
        ),
        Subscription(
            subscription_number="SUB-AUTO-CLOSE-2",
            customer_account_id=account.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            start_date=date.today() - timedelta(days=30),
            expiry_date=date.today(),
        ),
    ])
    await db_session.commit()

    closed_count = await _close_expired_subscriptions(
        db_session,
        today=date.today(),
        actor_user_id=admin.id,
    )

    expired = (await db_session.execute(
        select(Subscription).where(
            Subscription.subscription_number.like("SUB-AUTO-CLOSE-%")
        )
    )).scalars().all()
    assert closed_count == 1
    assert next(s for s in expired if s.subscription_number.endswith("1")).status == SubscriptionStatus.CLOSED
    assert next(s for s in expired if s.subscription_number.endswith("2")).status == SubscriptionStatus.ACTIVE
    audit = (await db_session.execute(
        select(AuditEvent).where(
            AuditEvent.entity_id == next(s for s in expired if s.subscription_number.endswith("1")).id,
            AuditEvent.action == "AUTO_CLOSE_ON_EXPIRY",
        )
    )).scalar_one()
    assert audit.actor_user_id == admin.id


@pytest.mark.asyncio
async def test_tax_rules_crud_and_validation(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    staff = seed_users["staff"]
    admin_cookies = auth_cookies(admin)
    staff_cookies = auth_cookies(staff)

    # 1. Staff forbidden to create tax rule
    res = await client.post(
        "/api/v1/tax-rules",
        json={"name": "State VAT", "rate_percentage": "10.00"},
        cookies=staff_cookies,
    )
    assert res.status_code == 403

    # 2. Validation error: Rate exceeds 100%
    res = await client.post(
        "/api/v1/tax-rules",
        json={"name": "Excessive Tax", "rate_percentage": "105.00"},
        cookies=admin_cookies,
    )
    assert res.status_code == 422

    # 3. Validation error: Negative rate
    res = await client.post(
        "/api/v1/tax-rules",
        json={"name": "Negative Tax", "rate_percentage": "-5.00"},
        cookies=admin_cookies,
    )
    assert res.status_code == 422

    # 4. Admin creates valid Tax Rule
    res = await client.post(
        "/api/v1/tax-rules",
        json={
            "name": "Standard VAT",
            "rate_percentage": "15.00",
            "is_active": True,
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 201
    tax_data = res.json()
    tax_id = tax_data["id"]
    assert tax_data["name"] == "Standard VAT"
    assert tax_data["rate_percentage"] == "15.00"
    assert tax_data["is_active"] is True

    # 5. List tax rules (accessible by authenticated users / staff)
    res = await client.get("/api/v1/tax-rules", cookies=staff_cookies)
    assert res.status_code == 200
    assert any(r["id"] == tax_id for r in res.json())

    # 6. Admin updates tax rule
    res = await client.put(
        f"/api/v1/tax-rules/{tax_id}",
        json={"rate_percentage": "16.50"},
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["rate_percentage"] == "16.50"

    # 7. Admin archives tax rule
    res = await client.delete(f"/api/v1/tax-rules/{tax_id}", cookies=admin_cookies)
    assert res.status_code == 200
    assert res.json()["is_active"] is False


@pytest.mark.asyncio
async def test_discount_rules_admin_only_and_caps(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    staff = seed_users["staff"]
    admin_cookies = auth_cookies(admin)
    staff_cookies = auth_cookies(staff)

    today = date.today()
    next_month = today + timedelta(days=30)

    # 1. Staff strictly forbidden from listing discount rules
    res = await client.get("/api/v1/discount-rules", cookies=staff_cookies)
    assert res.status_code == 403

    # 2. Staff forbidden from creating discount rule
    res = await client.post(
        "/api/v1/discount-rules",
        json={
            "name": "Staff Discount",
            "discount_type": "percentage",
            "value": "20.00",
            "valid_from": today.isoformat(),
            "valid_to": next_month.isoformat(),
        },
        cookies=staff_cookies,
    )
    assert res.status_code == 403

    # 3. Validation: Percentage > 100 rejected
    res = await client.post(
        "/api/v1/discount-rules",
        json={
            "name": "Over 100 Promo",
            "discount_type": "percentage",
            "value": "110.00",
            "valid_from": today.isoformat(),
            "valid_to": next_month.isoformat(),
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 422

    # 4. Validation: Invalid date range (valid_from > valid_to)
    res = await client.post(
        "/api/v1/discount-rules",
        json={
            "name": "Bad Dates Promo",
            "discount_type": "fixed",
            "value": "50.00",
            "valid_from": next_month.isoformat(),
            "valid_to": today.isoformat(),
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 422

    # 5. Admin creates valid percentage discount rule
    res = await client.post(
        "/api/v1/discount-rules",
        json={
            "name": "Launch Promo 20%",
            "discount_type": "percentage",
            "value": "20.00",
            "scope": "subscription",
            "min_spend": "100.00",
            "max_usage_limit": 50,
            "valid_from": today.isoformat(),
            "valid_to": next_month.isoformat(),
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 201
    disc_data = res.json()
    disc_id = disc_data["id"]
    assert disc_data["name"] == "Launch Promo 20%"
    assert disc_data["value"] == "20.00"
    assert disc_data["max_usage_limit"] == 50
    assert disc_data["current_usage_count"] == 0

    # 6. Admin updates discount rule
    res = await client.put(
        f"/api/v1/discount-rules/{disc_id}",
        json={"value": "25.00", "max_usage_limit": 100},
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["value"] == "25.00"
    assert res.json()["max_usage_limit"] == 100


@pytest.mark.asyncio
async def test_discount_partial_updates_persist_and_validate_merged_state(client: AsyncClient, seed_users):
    admin_cookies = auth_cookies(seed_users["admin"])
    today = date.today()
    next_month = today + timedelta(days=30)
    res = await client.post(
        "/api/v1/discount-rules",
        json={
            "name": "Partial Update Promo",
            "discount_type": "percentage",
            "value": "20.00",
            "valid_from": today.isoformat(),
            "valid_to": next_month.isoformat(),
            "max_usage_limit": 80,
        },
        cookies=admin_cookies,
    )
    assert res.status_code == 201
    discount_id = res.json()["id"]

    # Changes to fields that do not affect the discount's name/value must still commit.
    res = await client.patch(
        f"/api/v1/discount-rules/{discount_id}",
        json={"min_spend": "300.00", "min_quantity": 4, "max_usage_limit": None},
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["min_spend"] == "300.00"
    assert res.json()["min_quantity"] == 4
    assert res.json()["max_usage_limit"] is None

    # Validate the complete existing rule plus the partial request.
    res = await client.patch(
        f"/api/v1/discount-rules/{discount_id}",
        json={"value": "120.00"},
        cookies=admin_cookies,
    )
    assert res.status_code == 422
    res = await client.patch(
        f"/api/v1/discount-rules/{discount_id}",
        json={"valid_from": (next_month + timedelta(days=1)).isoformat()},
        cookies=admin_cookies,
    )
    assert res.status_code == 422
    res = await client.patch(
        f"/api/v1/discount-rules/{discount_id}",
        json={"scope": "product"},
        cookies=admin_cookies,
    )
    assert res.status_code == 422

    product_id = str(seed_users["product"].id)
    res = await client.patch(
        f"/api/v1/discount-rules/{discount_id}",
        json={"scope": "product", "target_product_id": product_id},
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["target_product_id"] == product_id

    res = await client.patch(
        f"/api/v1/discount-rules/{discount_id}",
        json={"scope": "subscription"},
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["scope"] == "subscription"
    assert res.json()["target_product_id"] is None


@pytest.mark.asyncio
async def test_product_scoped_discount_only_applies_to_target_product(client: AsyncClient, seed_users):
    admin_cookies = auth_cookies(seed_users["admin"])
    product_a = seed_users["product"]
    plan = seed_users["plan"]
    today = date.today()
    next_year = today + timedelta(days=365)

    product_b_response = await client.post(
        "/api/v1/products",
        json={
            "name": "Analytics Add-on",
            "type": "service",
            "sales_price": "200.00",
            "cost_price": "50.00",
        },
        cookies=admin_cookies,
    )
    assert product_b_response.status_code == 201
    product_b = product_b_response.json()

    discount_response = await client.post(
        "/api/v1/discount-rules",
        json={
            "name": "Targeted Core Discount",
            "discount_type": "percentage",
            "value": "10.00",
            "scope": "product",
            "target_product_id": str(product_a.id),
            "valid_from": today.isoformat(),
            "valid_to": next_year.isoformat(),
        },
        cookies=admin_cookies,
    )
    assert discount_response.status_code == 201

    preview = await client.post(
        "/api/v1/catalog/calculate-preview",
        json={
            "plan_id": str(plan.id),
            "product_lines": [
                {"product_id": str(product_a.id), "quantity": 1},
                {"product_id": product_b["id"], "quantity": 1},
            ],
            "discount_rule_id": discount_response.json()["id"],
        },
        cookies=admin_cookies,
    )
    assert preview.status_code == 200
    data = preview.json()
    assert data["subtotal"] == "500.00"
    assert data["discount_amount"] == "10.00"
    assert data["total_amount"] == "490.00"
    line_a = next(line for line in data["lines"] if line["product_name"] == product_a.name)
    line_b = next(line for line in data["lines"] if line["product_name"] == "Analytics Add-on")
    plan_line = next(line for line in data["lines"] if line["product_name"] == plan.name)
    assert line_a["discount_amount"] == "10.00"
    assert line_b["discount_amount"] == "0.00"
    assert plan_line["discount_amount"] == "0.00"


@pytest.mark.asyncio
async def test_price_preview_rejects_archived_items_and_wrong_variants(client: AsyncClient, seed_users):
    admin_cookies = auth_cookies(seed_users["admin"])
    product = seed_users["product"]
    plan = seed_users["plan"]
    variant = await client.post(
        f"/api/v1/products/{product.id}/variants",
        json={"name": "Standard", "price_adjustment": "0.00"},
        cookies=admin_cookies,
    )
    assert variant.status_code == 201

    product_b_response = await client.post(
        "/api/v1/products",
        json={"name": "Other Product", "type": "goods", "sales_price": "10.00", "cost_price": "4.00"},
        cookies=admin_cookies,
    )
    assert product_b_response.status_code == 201
    product_b_id = product_b_response.json()["id"]

    wrong_variant = await client.post(
        "/api/v1/catalog/calculate-preview",
        json={
            "plan_id": str(plan.id),
            "product_lines": [{"product_id": product_b_id, "variant_id": variant.json()["id"]}],
        },
        cookies=admin_cookies,
    )
    assert wrong_variant.status_code == 404

    await client.delete(f"/api/v1/products/{product.id}", cookies=admin_cookies)
    archived_product = await client.post(
        "/api/v1/catalog/calculate-preview",
        json={"product_lines": [{"product_id": str(product.id)}]},
        cookies=admin_cookies,
    )
    assert archived_product.status_code == 409


@pytest.mark.asyncio
async def test_calculate_preview_odoo_variant_tax_and_discounts(client: AsyncClient, seed_users):
    """
    Test the complete quote & calculation engine:
    - Base product: Brightloop Core ERP ($100.00)
    - Variant: Odoo Brand Edition (adds +$560.00) -> Unit Price: $660.00
    - Quantity: 2 -> Subtotal: $1320.00
    - Plan: Standard Monthly ($200.00) -> Plan line: $200.00
    - Subtotal: $1520.00
    - Discount: 10% Global/Subscription -> -$152.00
    - Taxable amount: $1368.00
    - Tax: 10% VAT -> +$136.80
    - Final Total: $1504.80
    Demonstrating exact adjustments and half-up rounding.
    """
    admin = seed_users["admin"]
    product = seed_users["product"]  # base price 100.00
    plan = seed_users["plan"]        # base price 200.00
    admin_cookies = auth_cookies(admin)

    today = date.today()
    next_year = today + timedelta(days=365)

    # 1. Create Odoo Brand variant with +560.00 adjustment
    res_var = await client.post(
        f"/api/v1/products/{product.id}/variants",
        json={
            "name": "Odoo Brand Edition",
            "price_adjustment": "560.00",
        },
        cookies=admin_cookies,
    )
    assert res_var.status_code == 201
    variant_id = res_var.json()["id"]

    # 2. Create 10% VAT Tax Rule
    res_tax = await client.post(
        "/api/v1/tax-rules",
        json={
            "name": "10% VAT",
            "rate_percentage": "10.00",
            "is_active": True,
        },
        cookies=admin_cookies,
    )
    assert res_tax.status_code == 201
    tax_rule_id = res_tax.json()["id"]

    # 3. Create 10% Subscription Discount Rule
    res_disc = await client.post(
        "/api/v1/discount-rules",
        json={
            "name": "10% Off Subscription",
            "discount_type": "percentage",
            "value": "10.00",
            "scope": "subscription",
            "valid_from": today.isoformat(),
            "valid_to": next_year.isoformat(),
        },
        cookies=admin_cookies,
    )
    assert res_disc.status_code == 201
    disc_id = res_disc.json()["id"]

    # 4. Run calculation preview
    preview_req = {
        "plan_id": str(plan.id),
        "product_lines": [
            {
                "product_id": str(product.id),
                "variant_id": str(variant_id),
                "quantity": 2,
            }
        ],
        "discount_rule_id": str(disc_id),
        "default_tax_rule_id": str(tax_rule_id),
    }

    res = await client.post(
        "/api/v1/catalog/calculate-preview",
        json=preview_req,
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    data = res.json()

    # Product line verification
    # Base: 100.00, Adjustment: 560.00 => Unit: 660.00. Qty: 2 => Subtotal: 1320.00
    prod_line = next(l for l in data["lines"] if l["product_name"] == product.name)
    assert prod_line["price_adjustment"] == "560.00"
    assert prod_line["unit_price"] == "660.00"
    assert prod_line["quantity"] == 2
    assert prod_line["subtotal"] == "1320.00"

    # Plan line verification
    plan_line = next(l for l in data["lines"] if "Plan Base Fee" in l["description"])
    assert plan_line["subtotal"] == "200.00"

    # Grand calculations
    # Subtotal: 1320.00 + 200.00 = 1520.00
    assert data["subtotal"] == "1520.00"
    # Discount 10%: 152.00
    assert data["discount_amount"] == "152.00"
    # Taxable: 1520.00 - 152.00 = 1368.00
    # Tax 10%: 136.80
    assert data["tax_amount"] == "136.80"
    # Total: 1368.00 + 136.80 = 1504.80
    assert data["total_amount"] == "1504.80"
    assert len(data["warnings"]) == 0
