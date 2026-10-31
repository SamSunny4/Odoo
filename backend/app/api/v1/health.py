from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.schemas.health import HealthCheckResponse

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse, tags=["System"])
async def check_health(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint verifying application runtime and database connectivity.
    """
    db_connected = False
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_connected = True
    except Exception:
        db_connected = False

    return HealthCheckResponse(
        status="ok" if db_connected else "degraded",
        database_connected=db_connected,
        environment=settings.ENVIRONMENT,
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
    )

