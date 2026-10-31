from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.products import router as products_router
from app.api.v1.subscriptions import router as subscriptions_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.payments import router as payments_router
from app.api.v1.control_tower import router as control_tower_router
from app.api.v1.portal import router as portal_router
from app.api.v1.reports import router as reports_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="", tags=["Health"])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(products_router, prefix="", tags=["Catalog"])
api_router.include_router(subscriptions_router, prefix="/subscriptions", tags=["Subscriptions"])
api_router.include_router(invoices_router, prefix="/invoices", tags=["Invoices"])
api_router.include_router(payments_router, prefix="/payments", tags=["Payments"])
api_router.include_router(control_tower_router, prefix="/control-tower", tags=["Control Tower"])
api_router.include_router(portal_router, prefix="/portal", tags=["Customer Portal"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
