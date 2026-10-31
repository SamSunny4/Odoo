from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    status: str  # "ok", "degraded", "unhealthy"
    database_connected: bool
    redis_connected: bool = True
    environment: str
    version: str = "1.0.0"
    timestamp: datetime
    outbox_failed_count: Optional[int] = 0
    stuck_billing_runs_count: Optional[int] = 0
    checks: Dict[str, Any] = {}
