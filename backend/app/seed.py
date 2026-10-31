import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.core.database import engine, AsyncSessionLocal, Base
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.customer import CustomerAccount, CustomerAccountMembership, CustomerMembershipRole
from app.models.catalog import Product, ProductVariant, ProductType
from app.models.plan import Plan, BillingCadence
from app.models.tax import TaxRule
from app.models.discount import DiscountRule, DiscountType, DiscountScope


async def seed_data():
    """Idempotent seed script provisioning initial admin, catalog, and test records."""
    print("🚀 Initializing Brightloop database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        print("🌱 Checking existing seeded users...")

        # 1. Admin User
        admin_email = "admin@brightloop.local"
        query_admin = select(User).where(User.email == admin_email)
        admin = (await session.execute(query_admin)).scalar_one_or_none()
        if not admin:
            admin = User(
                email=admin_email,
                hashed_password=get_password_hash("Admin@12345!"),
                full_name="Brightloop Administrator",
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin)
            print(f"  + Created Admin: {admin_email} (Password: Admin@12345!)")
        else:
            print(f"  - Admin already exists: {admin_email}")

        # 2. Staff User
        staff_email = "staff@brightloop.local"
        query_staff = select(User).where(User.email == staff_email)
        staff = (await session.execute(query_staff)).scalar_one_or_none()
        if not staff:
            staff = User(
                email=staff_email,
                hashed_password=get_password_hash("Staff@12345!"),
                full_name="Operations Staff",
                role=UserRole.STAFF,
                is_active=True,
            )
            session.add(staff)
            print(f"  + Created Staff: {staff_email} (Password: Staff@12345!)")
        else:
            print(f"  - Staff already exists: {staff_email}")

        # 3. Customer User & Account
        customer_email = "customer@acme.com"
        query_cust = select(User).where(User.email == customer_email)
        cust_user = (await session.execute(query_cust)).scalar_one_or_none()
        if not cust_user:
            cust_user = User(
                email=customer_email,
                hashed_password=get_password_hash("Customer@12345!"),
                full_name="Alex Mercer",
                role=UserRole.CUSTOMER,
                is_active=True,
            )
            session.add(cust_user)
            await session.flush()

            acme_account = CustomerAccount(
                company_name="Acme Corporation",
                billing_email=customer_email,
                phone="+1 (555) 234-5678",
                tax_id="US-TAX-987654321",
                billing_address_line1="100 Innovation Blvd",
                billing_city="Austin",
                billing_state="TX",
                billing_postal_code="78701",
                billing_country="US",
                currency="USD",
            )
            session.add(acme_account)
            await session.flush()

            membership = CustomerAccountMembership(
                customer_account_id=acme_account.id,
                user_id=cust_user.id,
                membership_role=CustomerMembershipRole.OWNER,
            )
            session.add(membership)
            print(f"  + Created Customer User & Account: {customer_email} (Password: Customer@12345!)")
        else:
            print(f"  - Customer already exists: {customer_email}")

        # 4. Products & Variants
        query_prod = select(Product).where(Product.name == "Brightloop Core ERP")
        prod = (await session.execute(query_prod)).scalar_one_or_none()
        if not prod:
            prod = Product(
                name="Brightloop Core ERP",
                type=ProductType.SERVICE,
                sales_price=Decimal("100.00"),
                cost_price=Decimal("30.00"),
                notes="Primary subscription software license.",
                is_active=True,
            )
            session.add(prod)
            await session.flush()

            odoo_variant = ProductVariant(
                product_id=prod.id,
                name="Brand: Odoo",
                price_adjustment=Decimal("560.00"),
                is_active=True,
            )
            session.add(odoo_variant)

            addon_prod = Product(
                name="Advanced Analytics Add-on",
                type=ProductType.SERVICE,
                sales_price=Decimal("45.00"),
                cost_price=Decimal("10.00"),
                notes="Real-time reporting and KPI dashboard add-on.",
                is_active=True,
            )
            session.add(addon_prod)
            print("  + Created Products (Brightloop Core ERP + Odoo Brand Variant + Analytics Add-on)")

        # 5. Plans
        query_plan = select(Plan).where(Plan.name == "Standard Business Monthly")
        plan = (await session.execute(query_plan)).scalar_one_or_none()
        if not plan:
            plan_monthly = Plan(
                name="Standard Business Monthly",
                cadence=BillingCadence.MONTHLY,
                base_price=Decimal("200.00"),
                min_quantity=1,
                auto_close_on_expiry=False,
                allow_early_close=True,
                allow_pause=True,
                allow_renewal=True,
                is_active=True,
            )
            plan_annual = Plan(
                name="Enterprise Annual Plan",
                cadence=BillingCadence.YEARLY,
                base_price=Decimal("2000.00"),
                min_quantity=5,
                auto_close_on_expiry=True,
                allow_early_close=False,
                allow_pause=True,
                allow_renewal=True,
                is_active=True,
            )
            session.add_all([plan_monthly, plan_annual])
            print("  + Created Plans (Monthly & Annual)")

        # 6. Tax Rules
        query_tax = select(TaxRule).where(TaxRule.name == "Standard Sales Tax 10%")
        tax = (await session.execute(query_tax)).scalar_one_or_none()
        if not tax:
            tax = TaxRule(
                name="Standard Sales Tax 10%",
                rate_percentage=Decimal("10.00"),
                is_active=True,
            )
            session.add(tax)
            print("  + Created Tax Rule (10%)")

        # 7. Discount Rules
        query_disc = select(DiscountRule).where(DiscountRule.name == "High Volume Tier Discount")
        discount = (await session.execute(query_disc)).scalar_one_or_none()
        if not discount:
            discount = DiscountRule(
                name="High Volume Tier Discount",
                discount_type=DiscountType.PERCENTAGE,
                value=Decimal("15.00"),
                scope=DiscountScope.SUBSCRIPTION,
                min_spend=Decimal("500.00"),
                min_quantity=5,
                max_usage_limit=100,
                valid_from=date.today(),
                valid_to=date.today() + timedelta(days=365),
                is_active=True,
            )
            session.add(discount)
            print("  + Created Discount Rule (15% High Volume)")

        await session.commit()
        print("✅ Database seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_data())

