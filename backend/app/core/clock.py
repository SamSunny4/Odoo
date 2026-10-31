from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def organization_today() -> date:
    """Return the current date in the configured business timezone."""
    return datetime.now(ZoneInfo(settings.ORGANIZATION_TIMEZONE)).date()
