import json
import logging
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = getattr(record, "request_id")
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging():
    """Configure structured logging based on runtime environment."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        if settings.is_production:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
        root_logger.addHandler(handler)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    HTTP Middleware assigning unique request correlation IDs and logging
    request execution times and outcomes.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Correlation ID from header or newly generated
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Inject correlation header in response
        response.headers["X-Request-ID"] = request_id

        logger = logging.getLogger("brightloop.access")
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} ({duration_ms:.1f}ms)",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "client_ip": request.client.host if request.client else "unknown",
            },
        )

        return response

