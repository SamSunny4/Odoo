from datetime import datetime
from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    status: str
    database_connected: bool
    environment: str
    version: str = "1.0.0"
    timestamp: datetime

