import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base
from app.core.database import get_db
from app.core.security import get_password_hash, create_access_token
from app.core.rate_limit import login_limiter, forgot_password_limiter, reset_password_limiter
from app.core.revocation import reset_revocations
from app.models.user import User, UserRole
from app.models.customer import CustomerAccount, CustomerAccountMembership, CustomerMembershipRole
from app.models.plan import Plan, BillingCadence
from app.models.catalog import Product, ProductType

# Precompute standard test password hash once to avoid repeated 350ms bcrypt delays in fixtures
PRECOMPUTED_HASH = get_password_hash("Brightloop@12345!")


@pytest_asyncio.fixture
async def test_engine():
    """Create in-memory SQLite async engine with StaticPool for test isolation."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False, "timeout": 5},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provide a single transactional async session for tests to prevent concurrent SQLite lock contention."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """
    Standard synchronous autouse fixture resetting rate limiters.
    Ensures Redis network I/O is disabled during tests to eliminate socket timeouts and stalls.
    """
    login_limiter.redis_enabled = False
    forgot_password_limiter.redis_enabled = False
    reset_password_limiter.redis_enabled = False

    login_limiter.reset()
    forgot_password_limiter.reset()
    reset_password_limiter.reset()
    yield
    login_limiter.reset()
    forgot_password_limiter.reset()
    reset_password_limiter.reset()


@pytest.fixture(autouse=True)
def reset_token_revocations():
    """Reset token revocation store before and after each test."""
    reset_revocations()
    yield
    reset_revocations()


@pytest_asyncio.fixture
async def client(db_session):
    """Provide an unauthenticated AsyncClient routed to the single shared test session."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_users(db_session):
    """Seed baseline admin, staff, and two distinct customers for isolation tests."""
    # 1. Admin
    admin = User(
        email="admin@brightloop.local",
        hashed_password=PRECOMPUTED_HASH,
        full_name="Brightloop Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)

    # 2. Staff
    staff = User(
        email="staff@brightloop.local",
        hashed_password=PRECOMPUTED_HASH,
        full_name="Operations Staff",
        role=UserRole.STAFF,
        is_active=True,
    )
    db_session.add(staff)

    # 3. Customer A (Acme Corp)
    customer_a = User(
        email="customer.a@acme.com",
        hashed_password=PRECOMPUTED_HASH,
        full_name="Alice Acme",
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    db_session.add(customer_a)
    await db_session.flush()

    account_a = CustomerAccount(
        company_name="Acme Corporation",
        billing_email="customer.a@acme.com",
        billing_address_line1="100 Innovation Blvd",
        billing_city="Austin",
        billing_postal_code="78701",
        billing_country="US",
        currency="USD",
    )
    db_session.add(account_a)
    await db_session.flush()

    db_session.add(CustomerAccountMembership(
        customer_account_id=account_a.id,
        user_id=customer_a.id,
        membership_role=CustomerMembershipRole.OWNER,
    ))

    # 4. Customer B (Beta Industries)
    customer_b = User(
        email="customer.b@beta.com",
        hashed_password=PRECOMPUTED_HASH,
        full_name="Bob Beta",
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    db_session.add(customer_b)
    await db_session.flush()

    account_b = CustomerAccount(
        company_name="Beta Industries",
        billing_email="customer.b@beta.com",
        billing_address_line1="200 Tech Park",
        billing_city="Seattle",
        billing_postal_code="98101",
        billing_country="US",
        currency="USD",
    )
    db_session.add(account_b)
    await db_session.flush()

    db_session.add(CustomerAccountMembership(
        customer_account_id=account_b.id,
        user_id=customer_b.id,
        membership_role=CustomerMembershipRole.OWNER,
    ))

    # 5. Sample Catalog
    product = Product(
        name="Brightloop Core ERP",
        type=ProductType.SERVICE,
        sales_price=100.00,
        cost_price=40.00,
        is_active=True,
    )
    db_session.add(product)

    plan = Plan(
        name="Standard Monthly",
        cadence=BillingCadence.MONTHLY,
        base_price=200.00,
        min_quantity=1,
        is_active=True,
    )
    db_session.add(plan)

    await db_session.commit()

    return {
        "admin": admin,
        "staff": staff,
        "customer_a": customer_a,
        "account_a": account_a,
        "customer_b": customer_b,
        "account_b": account_b,
        "product": product,
        "plan": plan,
    }


def auth_cookies(user: User) -> dict:
    """Helper creating session cookies for a given user."""
    token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )
    return {"brightloop_session": token}
