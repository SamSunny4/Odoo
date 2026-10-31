"""
Synthetic Demo & Seed Data Generator for Brightloop Subscription OS.
Populates rich, realistic Indian B2B customers, multi-tier catalog, subscriptions,
invoices across all lifecycle states, payments ledger, and collection queue aging buckets.
"""

import asyncio
import sys
import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
from sqlalchemy import select, delete
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.customer import CustomerAccount, CustomerAccountMembership, CustomerMembershipRole
from app.models.catalog import Product, ProductVariant, ProductType
from app.models.plan import Plan, BillingCadence
from app.models.tax import TaxRule
from app.models.discount import DiscountRule, DiscountType, DiscountScope
from app.models.subscription import Subscription, SubscriptionLine, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, SendStatus
from app.models.payment import Payment, PaymentMethod, PaymentReversal
from app.models.quote_template import QuotationTemplate


async def seed_data():
    """Seed comprehensive synthetic data into Brightloop PostgreSQL database."""
    async with AsyncSessionLocal() as session:
        print("==========================================================")
        print("  Brightloop Subscription OS - Synthetic Data Seeder     ")
        print("==========================================================")
        today = date.today()

        # ----------------------------------------------------
        # 1. CORE USERS (Admin & Staff)
        # ----------------------------------------------------
        admin_email = "admin@brightloop.local"
        admin = (await session.execute(select(User).where(User.email == admin_email))).scalar_one_or_none()
        if not admin:
            admin = User(
                email=admin_email,
                hashed_password=get_password_hash("Admin@12345!"),
                full_name="Brightloop Administrator",
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin)
            await session.flush()
            print(f"  + Admin: {admin_email} (Pass: Admin@12345!)")
        else:
            print(f"  - Admin exists: {admin_email}")

        staff_email = "staff@brightloop.local"
        staff = (await session.execute(select(User).where(User.email == staff_email))).scalar_one_or_none()
        if not staff:
            staff = User(
                email=staff_email,
                hashed_password=get_password_hash("Staff@12345!"),
                full_name="Pooja Sharma",
                role=UserRole.STAFF,
                is_active=True,
            )
            session.add(staff)
            await session.flush()
            print(f"  + Staff: {staff_email} (Pass: Staff@12345!)")
        else:
            print(f"  - Staff exists: {staff_email}")

        # ----------------------------------------------------
        # 2. B2B CUSTOMER COMPANIES & PORTAL USERS
        # ----------------------------------------------------
        customers_meta = [
            {
                "email": "customer@acme.com",
                "name": "Alex Mercer",
                "company": "Acme Corporation",
                "phone": "+91 98200 12345",
                "tax_id": "27AABCA1234A1Z5",
                "line1": "Level 14, Platina Tower, Bandra Kurla Complex",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postal": "400051",
            },
            {
                "email": "rahul.sharma@infosys-solutions.in",
                "name": "Rahul Sharma",
                "company": "Infosys Digital Solutions",
                "phone": "+91 80285 20261",
                "tax_id": "29AABCI5678B1Z4",
                "line1": "Electronics City, Phase 1, Hosur Road",
                "city": "Bengaluru",
                "state": "Karnataka",
                "postal": "560100",
            },
            {
                "email": "priya.patel@razorpay-connect.in",
                "name": "Priya Patel",
                "company": "Razorpay Integrations Ltd",
                "phone": "+91 80466 69555",
                "tax_id": "29AABCR9012C1Z3",
                "line1": "1st Floor, SJR Cyber, Hosur Road",
                "city": "Bengaluru",
                "state": "Karnataka",
                "postal": "560030",
            },
            {
                "email": "arjun.nair@swiggy-ops.in",
                "name": "Arjun Nair",
                "company": "Swiggy Logistics Network",
                "phone": "+91 80674 66777",
                "tax_id": "29AABCS3456D1Z2",
                "line1": "Maruthi Chambers, Survey No 17/9B",
                "city": "Bengaluru",
                "state": "Karnataka",
                "postal": "560068",
            },
            {
                "email": "vikram.singh@zomato-kitchens.in",
                "name": "Vikram Singh",
                "company": "Zomato Cloud Kitchens",
                "phone": "+91 12441 57777",
                "tax_id": "06AABCZ7890E1Z1",
                "line1": "Ground Floor, Tower C, Pioneer Urban Square",
                "city": "Gurugram",
                "state": "Haryana",
                "postal": "122102",
            },
            {
                "email": "ananya.deshmukh@tata-platforms.in",
                "name": "Ananya Deshmukh",
                "company": "Tata Digital Platforms",
                "phone": "+91 20660 70000",
                "tax_id": "27AABCT2345F1Z9",
                "line1": "Tata Management Training Centre, 1 Mangaldas Road",
                "city": "Pune",
                "state": "Maharashtra",
                "postal": "411001",
            },
            {
                "email": "rohit.verma@zepto-logistics.in",
                "name": "Rohit Verma",
                "company": "Zepto Quick Commerce",
                "phone": "+91 22489 70000",
                "tax_id": "27AABCZ6789G1Z8",
                "line1": "WeWork Enam Sambhav, C-20, G Block, BKC",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postal": "400051",
            },
            {
                "email": "neha.reddy@bel-cloud.in",
                "name": "Neha Reddy",
                "company": "Bharat Electronics Cloud",
                "phone": "+91 40271 20000",
                "tax_id": "36AABCB0123H1Z7",
                "line1": "Industrial Estate, Nacharam",
                "city": "Hyderabad",
                "state": "Telangana",
                "postal": "500076",
            },
        ]

        customer_map = {}
        for cdata in customers_meta:
            user_obj = (await session.execute(select(User).where(User.email == cdata["email"]))).scalar_one_or_none()
            if not user_obj:
                user_obj = User(
                    email=cdata["email"],
                    hashed_password=get_password_hash("Customer@12345!"),
                    full_name=cdata["name"],
                    role=UserRole.CUSTOMER,
                    is_active=True,
                )
                session.add(user_obj)
                await session.flush()

            acc_obj = (await session.execute(select(CustomerAccount).where(CustomerAccount.company_name == cdata["company"]))).scalar_one_or_none()
            if not acc_obj:
                acc_obj = CustomerAccount(
                    company_name=cdata["company"],
                    billing_email=cdata["email"],
                    phone=cdata["phone"],
                    tax_id=cdata["tax_id"],
                    billing_address_line1=cdata["line1"],
                    billing_city=cdata["city"],
                    billing_state=cdata["state"],
                    billing_postal_code=cdata["postal"],
                    billing_country="IN",
                    currency="INR",
                )
                session.add(acc_obj)
                await session.flush()

                mem = CustomerAccountMembership(
                    customer_account_id=acc_obj.id,
                    user_id=user_obj.id,
                    membership_role=CustomerMembershipRole.OWNER,
                )
                session.add(mem)
                print(f"  + Customer: {cdata['company']} ({cdata['email']})")
            else:
                acc_obj.currency = "INR"

            customer_map[cdata["company"]] = acc_obj

        # ----------------------------------------------------
        # 3. CATALOG PRODUCTS & VARIANTS
        # ----------------------------------------------------
        prods_meta = [
            {
                "name": "Brightloop Core ERP",
                "type": ProductType.SERVICE,
                "sales_price": Decimal("12000.00"),
                "cost_price": Decimal("3500.00"),
                "notes": "Primary enterprise subscription software license.",
                "is_add_on": False,
                "variants": [
                    {"name": "Brand: Odoo Enterprise", "adjustment": Decimal("8500.00")},
                    {"name": "Brand: SAP Business One", "adjustment": Decimal("15000.00")},
                ],
            },
            {
                "name": "Advanced Analytics & BI Add-on",
                "type": ProductType.SERVICE,
                "sales_price": Decimal("4500.00"),
                "cost_price": Decimal("1200.00"),
                "notes": "Real-time executive reporting, KPI charts, and anomaly monitoring.",
                "is_add_on": True,
                "variants": [],
            },
            {
                "name": "Multi-Warehouse Inventory Module",
                "type": ProductType.SERVICE,
                "sales_price": Decimal("7500.00"),
                "cost_price": Decimal("2000.00"),
                "notes": "Real-time multi-location inventory, transfer tracking, and batch control.",
                "is_add_on": True,
                "variants": [],
            },
            {
                "name": "24/7 Dedicated Priority Support",
                "type": ProductType.SERVICE,
                "sales_price": Decimal("5000.00"),
                "cost_price": Decimal("1500.00"),
                "notes": "15-minute SLA response, dedicated technical account manager.",
                "is_add_on": True,
                "variants": [],
            },
            {
                "name": "REST API & Webhooks Integration Pack",
                "type": ProductType.SERVICE,
                "sales_price": Decimal("3500.00"),
                "cost_price": Decimal("800.00"),
                "notes": "High-throughput API endpoints and webhook subscription dispatcher.",
                "is_add_on": True,
                "variants": [],
            },
            {
                "name": "Automated GST & E-Invoicing Gateway",
                "type": ProductType.SERVICE,
                "sales_price": Decimal("2500.00"),
                "cost_price": Decimal("500.00"),
                "notes": "Direct NIC e-way bill and GST portal IRN generation connector.",
                "is_add_on": True,
                "variants": [],
            },
        ]

        product_map = {}
        variant_map = {}
        for pdata in prods_meta:
            p_obj = (await session.execute(select(Product).where(Product.name == pdata["name"]))).scalar_one_or_none()
            if not p_obj:
                p_obj = Product(
                    name=pdata["name"],
                    type=pdata["type"],
                    sales_price=pdata["sales_price"],
                    cost_price=pdata["cost_price"],
                    notes=pdata["notes"],
                    is_add_on=pdata["is_add_on"],
                    is_active=True,
                )
                session.add(p_obj)
                await session.flush()
                print(f"  + Product: {pdata['name']} (INR {pdata['sales_price']})")
                for v in pdata["variants"]:
                    v_obj = ProductVariant(
                        product_id=p_obj.id,
                        name=v["name"],
                        price_adjustment=v["adjustment"],
                        is_active=True,
                    )
                    session.add(v_obj)
                    await session.flush()
                    variant_map[v["name"]] = v_obj
            else:
                p_obj.sales_price = pdata["sales_price"]
                # load variants
                v_res = (await session.execute(select(ProductVariant).where(ProductVariant.product_id == p_obj.id))).scalars().all()
                for v in v_res:
                    variant_map[v.name] = v

            product_map[pdata["name"]] = p_obj

        # ----------------------------------------------------
        # 4. PLANS
        # ----------------------------------------------------
        plans_meta = [
            {
                "name": "Standard Business Monthly",
                "cadence": BillingCadence.MONTHLY,
                "base_price": Decimal("2500.00"),
                "min_quantity": 1,
                "allow_early_close": True,
                "allow_pause": True,
                "allow_renewal": True,
                "auto_close_on_expiry": False,
            },
            {
                "name": "Growth Scale Monthly",
                "cadence": BillingCadence.MONTHLY,
                "base_price": Decimal("7500.00"),
                "min_quantity": 1,
                "allow_early_close": True,
                "allow_pause": True,
                "allow_renewal": True,
                "auto_close_on_expiry": False,
            },
            {
                "name": "Enterprise Annual Suite",
                "cadence": BillingCadence.YEARLY,
                "base_price": Decimal("75000.00"),
                "min_quantity": 3,
                "allow_early_close": False,
                "allow_pause": True,
                "allow_renewal": True,
                "auto_close_on_expiry": True,
            },
            {
                "name": "Startup Sprint Weekly",
                "cadence": BillingCadence.WEEKLY,
                "base_price": Decimal("850.00"),
                "min_quantity": 1,
                "allow_early_close": True,
                "allow_pause": True,
                "allow_renewal": True,
                "auto_close_on_expiry": False,
            },
        ]

        plan_map = {}
        for pl in plans_meta:
            pl_obj = (await session.execute(select(Plan).where(Plan.name == pl["name"]))).scalar_one_or_none()
            if not pl_obj:
                pl_obj = Plan(
                    name=pl["name"],
                    cadence=pl["cadence"],
                    base_price=pl["base_price"],
                    min_quantity=pl["min_quantity"],
                    allow_early_close=pl["allow_early_close"],
                    allow_pause=pl["allow_pause"],
                    allow_renewal=pl["allow_renewal"],
                    auto_close_on_expiry=pl["auto_close_on_expiry"],
                    is_active=True,
                )
                session.add(pl_obj)
                await session.flush()
                print(f"  + Plan: {pl['name']} (INR {pl['base_price']})")
            else:
                pl_obj.base_price = pl["base_price"]

            plan_map[pl["name"]] = pl_obj

        # ----------------------------------------------------
        # 5. TAX RULES
        # ----------------------------------------------------
        taxes_meta = [
            {"name": "GST 18% (Standard IT Services)", "rate": Decimal("18.00")},
            {"name": "GST 12% (Concessional Rate)", "rate": Decimal("12.00")},
            {"name": "GST 5% (Exempt Services)", "rate": Decimal("5.00")},
        ]
        tax_map = {}
        for tm in taxes_meta:
            t_obj = (await session.execute(select(TaxRule).where(TaxRule.name == tm["name"]))).scalar_one_or_none()
            if not t_obj:
                t_obj = TaxRule(name=tm["name"], rate_percentage=tm["rate"], is_active=True)
                session.add(t_obj)
                await session.flush()
                print(f"  + Tax Rule: {tm['name']}")
            tax_map[tm["name"]] = t_obj

        gst_18 = tax_map["GST 18% (Standard IT Services)"]

        # ----------------------------------------------------
        # 6. DISCOUNT RULES
        # ----------------------------------------------------
        disc_meta = [
            {
                "name": "Early-Stage Startup Launch (10%)",
                "type": DiscountType.PERCENTAGE,
                "value": Decimal("10.00"),
                "scope": DiscountScope.SUBSCRIPTION,
                "min_spend": Decimal("5000.00"),
                "min_quantity": 1,
                "max_usage_limit": 50,
            },
            {
                "name": "Enterprise Volume Scale (15%)",
                "type": DiscountType.PERCENTAGE,
                "value": Decimal("15.00"),
                "scope": DiscountScope.SUBSCRIPTION,
                "min_spend": Decimal("25000.00"),
                "min_quantity": 3,
                "max_usage_limit": 100,
            },
            {
                "name": "Annual Prepay Discount (₹5,000 Off)",
                "type": DiscountType.FIXED,
                "value": Decimal("5000.00"),
                "scope": DiscountScope.SUBSCRIPTION,
                "min_spend": Decimal("50000.00"),
                "min_quantity": 1,
                "max_usage_limit": 25,
            },
        ]
        disc_map = {}
        for dm in disc_meta:
            d_obj = (await session.execute(select(DiscountRule).where(DiscountRule.name == dm["name"]))).scalar_one_or_none()
            if not d_obj:
                d_obj = DiscountRule(
                    name=dm["name"],
                    discount_type=dm["type"],
                    value=dm["value"],
                    scope=dm["scope"],
                    min_spend=dm["min_spend"],
                    min_quantity=dm["min_quantity"],
                    max_usage_limit=dm["max_usage_limit"],
                    valid_from=today - timedelta(days=60),
                    valid_to=today + timedelta(days=300),
                    is_active=True,
                )
                session.add(d_obj)
                await session.flush()
                print(f"  + Discount Rule: {dm['name']}")
            disc_map[dm["name"]] = d_obj

        # ----------------------------------------------------
        # 7. QUOTATION TEMPLATES
        # ----------------------------------------------------
        qt_name1 = "Growth Tier Starter Template"
        qt1 = (await session.execute(select(QuotationTemplate).where(QuotationTemplate.name == qt_name1))).scalar_one_or_none()
        if not qt1:
            qt1 = QuotationTemplate(
                name=qt_name1,
                validity_days=30,
                default_plan_id=plan_map["Growth Scale Monthly"].id,
                default_lines=[
                    {"product_id": str(product_map["Brightloop Core ERP"].id), "quantity": 1},
                    {"product_id": str(product_map["Advanced Analytics & BI Add-on"].id), "quantity": 1},
                ],
            )
            session.add(qt1)
            print(f"  + Quotation Template: {qt_name1}")

        qt_name2 = "Enterprise Full-Stack Suite"
        qt2 = (await session.execute(select(QuotationTemplate).where(QuotationTemplate.name == qt_name2))).scalar_one_or_none()
        if not qt2:
            qt2 = QuotationTemplate(
                name=qt_name2,
                validity_days=45,
                default_plan_id=plan_map["Enterprise Annual Suite"].id,
                default_lines=[
                    {"product_id": str(product_map["Brightloop Core ERP"].id), "quantity": 3},
                    {"product_id": str(product_map["Multi-Warehouse Inventory Module"].id), "quantity": 1},
                    {"product_id": str(product_map["24/7 Dedicated Priority Support"].id), "quantity": 1},
                ],
            )
            session.add(qt2)
            print(f"  + Quotation Template: {qt_name2}")

        await session.flush()

        # ----------------------------------------------------
        # 8. SUBSCRIPTIONS ACROSS LIFECYCLE
        # ----------------------------------------------------
        subs_meta = [
            {
                "num": "SUB-2026-0001",
                "company": "Acme Corporation",
                "plan": "Standard Business Monthly",
                "status": SubscriptionStatus.ACTIVE,
                "start": today - timedelta(days=60),
                "next_bill": today,  # Due today -> Control Tower previewable!
                "lines": [
                    {"prod": "Brightloop Core ERP", "qty": 1, "price": Decimal("20500.00")},
                    {"prod": "Advanced Analytics & BI Add-on", "qty": 1, "price": Decimal("4500.00")},
                ]
            },
            {
                "num": "SUB-2026-0002",
                "company": "Infosys Digital Solutions",
                "plan": "Growth Scale Monthly",
                "status": SubscriptionStatus.ACTIVE,
                "start": today - timedelta(days=45),
                "next_bill": today,  # Due today -> Control Tower previewable!
                "lines": [
                    {"prod": "Brightloop Core ERP", "qty": 2, "price": Decimal("12000.00")},
                    {"prod": "Multi-Warehouse Inventory Module", "qty": 1, "price": Decimal("7500.00")},
                ]
            },
            {
                "num": "SUB-2026-0003",
                "company": "Razorpay Integrations Ltd",
                "plan": "Enterprise Annual Suite",
                "status": SubscriptionStatus.ACTIVE,
                "start": today - timedelta(days=90),
                "next_bill": today,  # Due today -> Control Tower previewable!
                "lines": [
                    {"prod": "Brightloop Core ERP", "qty": 5, "price": Decimal("12000.00")},
                    {"prod": "24/7 Dedicated Priority Support", "qty": 1, "price": Decimal("5000.00")},
                ]
            },
            {
                "num": "SUB-2026-0004",
                "company": "Swiggy Logistics Network",
                "plan": "Growth Scale Monthly",
                "status": SubscriptionStatus.ACTIVE,
                "start": today - timedelta(days=20),
                "next_bill": today + timedelta(days=10),
                "lines": [
                    {"prod": "Brightloop Core ERP", "qty": 1, "price": Decimal("12000.00")},
                    {"prod": "REST API & Webhooks Integration Pack", "qty": 2, "price": Decimal("3500.00")},
                ]
            },
            {
                "num": "SUB-2026-0005",
                "company": "Zomato Cloud Kitchens",
                "plan": "Standard Business Monthly",
                "status": SubscriptionStatus.ACTIVE,
                "start": today - timedelta(days=15),
                "next_bill": today + timedelta(days=15),
                "lines": [
                    {"prod": "Brightloop Core ERP", "qty": 1, "price": Decimal("12000.00")},
                ]
            },
            {
                "num": "SUB-2026-0006",
                "company": "Tata Digital Platforms",
                "plan": "Enterprise Annual Suite",
                "status": SubscriptionStatus.QUOTATION,
                "start": today + timedelta(days=5),
                "next_bill": None,
                "quote_valid_until": today + timedelta(days=25),
                "lines": [
                    {"prod": "Brightloop Core ERP", "qty": 10, "price": Decimal("12000.00")},
                    {"prod": "Automated GST & E-Invoicing Gateway", "qty": 1, "price": Decimal("2500.00")},
                ]
            },
            {
                "num": "SUB-2026-0007",
                "company": "Zepto Quick Commerce",
                "plan": "Startup Sprint Weekly",
                "status": SubscriptionStatus.DRAFT,
                "start": today + timedelta(days=2),
                "next_bill": None,
                "lines": [
                    {"prod": "Brightloop Core ERP", "qty": 1, "price": Decimal("12000.00")},
                ]
            },
            {
                "num": "SUB-2026-0008",
                "company": "Bharat Electronics Cloud",
                "plan": "Standard Business Monthly",
                "status": SubscriptionStatus.PAUSED,
                "start": today - timedelta(days=120),
                "next_bill": None,
                "lines": [
                    {"prod": "Brightloop Core ERP", "qty": 1, "price": Decimal("12000.00")},
                ]
            },
        ]

        sub_map = {}
        for sm in subs_meta:
            s_obj = (await session.execute(select(Subscription).where(Subscription.subscription_number == sm["num"]))).scalar_one_or_none()
            c_acc = customer_map[sm["company"]]
            p_obj = plan_map[sm["plan"]]

            if not s_obj:
                s_obj = Subscription(
                    subscription_number=sm["num"],
                    customer_account_id=c_acc.id,
                    plan_id=p_obj.id,
                    status=sm["status"],
                    start_date=sm["start"],
                    next_billing_date=sm["next_bill"],
                    quote_valid_until=sm.get("quote_valid_until"),
                    billing_anchor_day=1,
                    payment_terms_days=15,
                )
                session.add(s_obj)
                await session.flush()
                for l in sm["lines"]:
                    prod = product_map[l["prod"]]
                    sl = SubscriptionLine(
                        subscription_id=s_obj.id,
                        product_id=prod.id,
                        quantity=l["qty"],
                        unit_price=l["price"],
                        tax_rule_id=gst_18.id,
                    )
                    session.add(sl)
                await session.flush()
                print(f"  + Subscription: {sm['num']} ({sm['status'].value} | {sm['company']})")
            else:
                s_obj.status = sm["status"]
                s_obj.next_billing_date = sm["next_bill"]

            sub_map[sm["num"]] = s_obj

        # ----------------------------------------------------
        # 9. INVOICES ACROSS ALL LIFECYCLE STATES & AGING BUCKETS
        # ----------------------------------------------------
        invoices_meta = [
            {
                "num": "INV-2026-0001",
                "sub": "SUB-2026-0001",
                "company": "Acme Corporation",
                "status": InvoiceStatus.PAID,
                "issue_offset": -60,
                "due_offset": -45,
                "subtotal": Decimal("25000.00"),
                "tax": Decimal("4500.00"),
                "total": Decimal("29500.00"),
                "paid": Decimal("29500.00"),
                "desc": "October Monthly Enterprise License",
            },
            {
                "num": "INV-2026-0002",
                "sub": "SUB-2026-0002",
                "company": "Infosys Digital Solutions",
                "status": InvoiceStatus.PAID,
                "issue_offset": -30,
                "due_offset": -15,
                "subtotal": Decimal("31500.00"),
                "tax": Decimal("5670.00"),
                "total": Decimal("37170.00"),
                "paid": Decimal("37170.00"),
                "desc": "Growth ERP & Multi-Warehouse Platform",
            },
            {
                "num": "INV-2026-0003",
                "sub": "SUB-2026-0003",
                "company": "Razorpay Integrations Ltd",
                "status": InvoiceStatus.CONFIRMED,
                "issue_offset": -20,
                "due_offset": -5,
                "subtotal": Decimal("65000.00"),
                "tax": Decimal("11700.00"),
                "total": Decimal("76700.00"),
                "paid": Decimal("40000.00"),  # Partially paid (₹36,700 outstanding)
                "desc": "Enterprise Suite Q4 Milestone",
            },
            {
                "num": "INV-2026-0004",
                "sub": "SUB-2026-0004",
                "company": "Swiggy Logistics Network",
                "status": InvoiceStatus.CONFIRMED,
                "issue_offset": -35,
                "due_offset": -15,  # 15 days overdue -> Aging: 1-30 Days Bucket
                "subtotal": Decimal("19000.00"),
                "tax": Decimal("3420.00"),
                "total": Decimal("22420.00"),
                "paid": Decimal("0.00"),
                "desc": "Swiggy Hyperlocal Fleet Dispatch Integration",
            },
            {
                "num": "INV-2026-0005",
                "sub": "SUB-2026-0005",
                "company": "Zomato Cloud Kitchens",
                "status": InvoiceStatus.CONFIRMED,
                "issue_offset": -65,
                "due_offset": -45,  # 45 days overdue -> Aging: 31-60 Days Bucket
                "subtotal": Decimal("12000.00"),
                "tax": Decimal("2160.00"),
                "total": Decimal("14160.00"),
                "paid": Decimal("0.00"),
                "desc": "Cloud Kitchen Inventory & POS Subscriptions",
            },
            {
                "num": "INV-2026-0006",
                "sub": "SUB-2026-0001",
                "company": "Tata Digital Platforms",
                "status": InvoiceStatus.CONFIRMED,
                "issue_offset": -95,
                "due_offset": -75,  # 75 days overdue -> Aging: 61-90 Days Bucket
                "subtotal": Decimal("48000.00"),
                "tax": Decimal("8640.00"),
                "total": Decimal("56640.00"),
                "paid": Decimal("10000.00"),  # ₹46,640 overdue
                "desc": "Tata Digital Platform Integration Services",
            },
            {
                "num": "INV-2026-0007",
                "sub": "SUB-2026-0002",
                "company": "Zepto Quick Commerce",
                "status": InvoiceStatus.CONFIRMED,
                "issue_offset": -130,
                "due_offset": -110,  # 110 days overdue -> Aging: 90+ Days Bucket
                "subtotal": Decimal("35000.00"),
                "tax": Decimal("6300.00"),
                "total": Decimal("41300.00"),
                "paid": Decimal("0.00"),
                "desc": "Zepto Rapid Logistics Dark-Store Subscriptions",
            },
            {
                "num": "INV-2026-0008",
                "sub": "SUB-2026-0003",
                "company": "Bharat Electronics Cloud",
                "status": InvoiceStatus.CONFIRMED,
                "issue_offset": -2,
                "due_offset": 13,  # Future due date -> Not overdue
                "subtotal": Decimal("14500.00"),
                "tax": Decimal("2610.00"),
                "total": Decimal("17110.00"),
                "paid": Decimal("0.00"),
                "desc": "Defence Automation Hardware & Gateway Connector",
            },
            {
                "num": "INV-2026-0009",
                "sub": "SUB-2026-0001",
                "company": "Acme Corporation",
                "status": InvoiceStatus.CANCELLED,
                "issue_offset": -15,
                "due_offset": 0,
                "subtotal": Decimal("8000.00"),
                "tax": Decimal("1440.00"),
                "total": Decimal("9440.00"),
                "paid": Decimal("0.00"),
                "desc": "Voided billing test replaced by consolidated run",
                "cancel_reason": "Superseded by consolidated annual agreement",
            },
        ]

        inv_map = {}
        for im in invoices_meta:
            inv_obj = (await session.execute(select(Invoice).where(Invoice.invoice_number == im["num"]))).scalar_one_or_none()
            c_acc = customer_map[im["company"]]
            sub_obj = sub_map[im["sub"]]
            issue_d = today + timedelta(days=im["issue_offset"])
            due_d = today + timedelta(days=im["due_offset"])

            if not inv_obj:
                inv_obj = Invoice(
                    invoice_number=im["num"],
                    subscription_id=sub_obj.id,
                    customer_account_id=c_acc.id,
                    idempotency_key=f"sub_{sub_obj.id}_{im['num']}",
                    currency="INR",
                    status=im["status"],
                    billing_period_start=issue_d,
                    billing_period_end=due_d,
                    subtotal=im["subtotal"],
                    tax_amount=im["tax"],
                    discount_amount=Decimal("0.00"),
                    total_amount=im["total"],
                    paid_amount=im["paid"],
                    issue_date=issue_d,
                    due_date=due_d,
                    send_status=SendStatus.SENT,
                    cancellation_reason=im.get("cancel_reason"),
                    customer_snapshot={
                        "company_name": c_acc.company_name,
                        "billing_email": c_acc.billing_email,
                        "tax_id": c_acc.tax_id,
                    },
                    billing_address_snapshot={
                        "address": c_acc.billing_address_line1,
                        "city": c_acc.billing_city,
                        "postal_code": c_acc.billing_postal_code,
                        "country": c_acc.billing_country,
                    },
                    lines=[
                        InvoiceLine(
                            description=im["desc"],
                            product_name_snapshot="Brightloop Core ERP",
                            quantity=1,
                            unit_price_snapshot=im["subtotal"],
                            subtotal=im["subtotal"],
                            tax_rule_name_snapshot="GST 18%",
                            tax_rate_snapshot=Decimal("18.00"),
                            tax_amount=im["tax"],
                            line_total=im["total"],
                        )
                    ],
                )
                session.add(inv_obj)
                await session.flush()
                print(f"  + Invoice: {im['num']} ({im['status'].value} | INR {im['total']} | {im['company']})")
            else:
                inv_obj.currency = "INR"
                inv_obj.total_amount = im["total"]
                inv_obj.paid_amount = im["paid"]
                inv_obj.due_date = due_d

            inv_map[im["num"]] = inv_obj

        # ----------------------------------------------------
        # 10. PAYMENTS & REVERSALS LEDGER
        # ----------------------------------------------------
        payments_meta = [
            {
                "inv": "INV-2026-0001",
                "amount": Decimal("29500.00"),
                "method": PaymentMethod.BANK_TRANSFER,
                "days_offset": -45,
                "note": "Full remittance via NEFT/RTGS Ref #AXIS982341",
                "reversals": [],
            },
            {
                "inv": "INV-2026-0002",
                "amount": Decimal("20000.00"),
                "method": PaymentMethod.BANK_TRANSFER,
                "days_offset": -14,
                "note": "1st tranche payment via HDFC Corporate Banking",
                "reversals": [],
            },
            {
                "inv": "INV-2026-0002",
                "amount": Decimal("17170.00"),
                "method": PaymentMethod.CREDIT_CARD,
                "days_offset": -10,
                "note": "2nd tranche final settlement via Corporate Visa",
                "reversals": [],
            },
            {
                "inv": "INV-2026-0003",
                "amount": Decimal("40000.00"),
                "method": PaymentMethod.BANK_TRANSFER,
                "days_offset": -4,
                "note": "Advance milestone payment Ref #ICICI77492",
                "reversals": [
                    {
                        "amount": Decimal("5000.00"),
                        "reason": "Customer SLA compensation refund approved by finance",
                        "days_offset": -2,
                    }
                ],
            },
            {
                "inv": "INV-2026-0006",
                "amount": Decimal("10000.00"),
                "method": PaymentMethod.BANK_TRANSFER,
                "days_offset": -50,
                "note": "Goodwill partial remittance against past-due invoice",
                "reversals": [],
            },
        ]

        for pm in payments_meta:
            inv_obj = inv_map[pm["inv"]]
            p_date = today + timedelta(days=pm["days_offset"])

            # Check existing payment for this invoice and amount
            existing_p = (
                await session.execute(
                    select(Payment).where(
                        Payment.invoice_id == inv_obj.id,
                        Payment.amount == pm["amount"],
                    )
                )
            ).scalar_one_or_none()

            if not existing_p:
                p_obj = Payment(
                    invoice_id=inv_obj.id,
                    amount=pm["amount"],
                    payment_method=pm["method"],
                    payment_date=p_date,
                    reference_note=pm["note"],
                    recorded_by_user_id=staff.id,
                    is_reversed=False,
                )
                session.add(p_obj)
                await session.flush()
                print(f"  + Payment: INR {pm['amount']} on {pm['inv']} ({pm['method'].value})")

                for rev in pm["reversals"]:
                    rev_date = datetime.now(timezone.utc) - timedelta(days=abs(rev["days_offset"]))
                    reversal_obj = PaymentReversal(
                        payment_id=p_obj.id,
                        reversal_amount=rev["amount"],
                        reason=rev["reason"],
                        reversed_by_user_id=admin.id,
                        reversed_at=rev_date,
                    )
                    session.add(reversal_obj)
                    await session.flush()
                    print(f"    * Payment Reversal/Refund: INR {rev['amount']} (Reason: {rev['reason']})")

        await session.commit()
        print("==========================================================")
        print("  Synthetic Data Generation Successfully Completed!      ")
        print("==========================================================")


if __name__ == "__main__":
    asyncio.run(seed_data())
