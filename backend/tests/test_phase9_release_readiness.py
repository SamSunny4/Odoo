import pytest
from httpx import AsyncClient
from app.core.config import Settings, DEVELOPMENT_SECRET_KEY


@pytest.mark.asyncio
async def test_healthcheck_endpoint_and_readiness(client: AsyncClient):
    # Test both root and api/v1 health endpoints
    for url in ["/health", "/api/v1/health"]:
        res = await client.get(url)
        assert res.status_code in (200, 503)
        data = res.json()
        assert "status" in data
        assert "database_connected" in data
        assert "version" in data
        assert "timestamp" in data
        assert "checks" in data
        assert data["database_connected"] is True


@pytest.mark.asyncio
async def test_structured_logging_correlation_and_middleware(client: AsyncClient):
    # 1. Custom correlation ID passed in header
    custom_id = "trace-req-849204820"
    res1 = await client.get("/health", headers={"X-Request-ID": custom_id})
    assert res1.status_code == 200
    assert res1.headers.get("X-Request-ID") == custom_id

    # 2. No correlation ID header -> auto-generated UUID returned
    res2 = await client.get("/health")
    assert res2.status_code == 200
    assert "X-Request-ID" in res2.headers
    assert len(res2.headers["X-Request-ID"]) >= 16


def test_production_secret_key_validation():
    # Production with default insecure key must fail validation
    with pytest.raises(ValueError, match="Production requires a unique SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=DEVELOPMENT_SECRET_KEY,
        )

    # Production with short secret key must fail validation
    with pytest.raises(ValueError, match="Production requires a unique SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="short-secret",
        )

    # Production with valid 32+ char key must pass
    valid_key = "x" * 48
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=valid_key,
    )
    assert s.is_production is True
    assert s.effective_cookie_secure is True


@pytest.mark.asyncio
async def test_root_discovery_endpoint(client: AsyncClient):
    res = await client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert "project" in data
    assert "documentation" in data
    assert "health" in data

