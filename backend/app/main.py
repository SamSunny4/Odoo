from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine
from app.core.logging import setup_logging, StructuredLoggingMiddleware
from app.api.v1.router import api_router
from app.api.v1.health import check_health

# Initialize structured logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Release database connections on application shutdown."""
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Brightloop Software — Subscription Management System API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Structured request correlation & performance logging
app.add_middleware(StructuredLoggingMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_router, prefix="/api/v1")

# Root liveness probe for load balancers and Kubernetes
app.add_api_route("/health", check_health, methods=["GET"], tags=["System"], include_in_schema=True)


@app.get("/")
def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": "1.0.0",
        "documentation": "/docs",
        "health": "/api/v1/health",
    }
