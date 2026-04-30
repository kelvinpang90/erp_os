"""
ERP OS — FastAPI application entry point.

Startup order:
  1. configure_logging()            structlog JSON/console
  2. RequestIDMiddleware            UUID4 per request
  3. CORSMiddleware                 whitelist origins
  4. slowapi state                  rate limit counters in Redis DB 3
  5. Exception handlers             AppException → uniform JSON
  6. Routers                        /api/auth/*, /health

All middleware is added in reverse order of execution (outermost last in code).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import AppException, RateLimitError
from app.core.logging import RequestIDMiddleware, configure_logging, get_request_id
from app.core.redis import ping_redis
from app.events import event_bus
from app.events.registry import setup_event_handlers
from app.routers import ai as ai_router
from app.routers import auth as auth_router
from app.routers import brand as brand_router
from app.routers import category as category_router
from app.routers import credit_note as credit_note_router
from app.routers import currency as currency_router
from app.routers import customer as customer_router
from app.routers import exchange_rate as exchange_rate_router
from app.routers import goods_receipt as goods_receipt_router
from app.routers import inventory as inventory_router
from app.routers import invoice as invoice_router
from app.routers import purchase_order as purchase_order_router
from app.routers import sales_order as sales_order_router
from app.routers import delivery_order as delivery_order_router
from app.routers import sku as sku_router
from app.routers import stock_adjustment as stock_adjustment_router
from app.routers import stock_transfer as stock_transfer_router
from app.routers import supplier as supplier_router
from app.routers import tax_rate as tax_rate_router
from app.routers import uom as uom_router
from app.routers import warehouse as warehouse_router

logger = structlog.get_logger()

# ── Rate limiter (slowapi) ────────────────────────────────────────────────────

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"{settings.redis_url}/{settings.REDIS_DB_RATE}",
    default_limits=["100/minute"],
)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    configure_logging()
    setup_event_handlers(event_bus)
    logger.info(
        "startup",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        demo_mode=settings.DEMO_MODE,
    )
    yield
    await engine.dispose()
    logger.info("shutdown")


# ── Application factory ───────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Attach limiter to app state (required by slowapi)
app.state.limiter = limiter


# ── Middleware ────────────────────────────────────────────────────────────────
# NOTE: FastAPI/Starlette applies middleware in reverse order of add_middleware().
# We want: RequestID → CORS → app
# So we add CORS first, then RequestID.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)


# ── Exception handlers ────────────────────────────────────────────────────────

def _error_body(
    error_code: str,
    message: str,
    detail: dict | None = None,
) -> dict[str, Any]:
    return {
        "error_code": error_code,
        "message": message,
        "request_id": get_request_id(),
        "timestamp": datetime.now(UTC).isoformat(),
        "detail": detail,
    }


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    logger.warning(
        "app_exception",
        error_code=exc.error_code,
        message=exc.message,
        http_status=exc.http_status,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=_error_body(exc.error_code, exc.message, exc.detail),
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    err = RateLimitError()
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=_error_body(err.error_code, str(exc.detail) or err.message),
        headers={"Retry-After": "60"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body(
            "VALIDATION_ERROR",
            "Request validation failed.",
            {"errors": exc.errors()},
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("INTERNAL_ERROR", "An unexpected error occurred."),
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(brand_router.router, prefix="/api/brands", tags=["brands"])
app.include_router(category_router.router, prefix="/api/categories", tags=["categories"])
app.include_router(uom_router.router, prefix="/api/uoms", tags=["uoms"])
app.include_router(tax_rate_router.router, prefix="/api/tax-rates", tags=["tax-rates"])
app.include_router(currency_router.router, prefix="/api/currencies", tags=["currencies"])
app.include_router(exchange_rate_router.router, prefix="/api/exchange-rates", tags=["exchange-rates"])
app.include_router(sku_router.router, prefix="/api/skus", tags=["skus"])
app.include_router(supplier_router.router, prefix="/api/suppliers", tags=["suppliers"])
app.include_router(customer_router.router, prefix="/api/customers", tags=["customers"])
app.include_router(warehouse_router.router, prefix="/api/warehouses", tags=["warehouses"])
app.include_router(purchase_order_router.router, prefix="/api/purchase-orders", tags=["purchase-orders"])
app.include_router(goods_receipt_router.router, prefix="/api/goods-receipts", tags=["goods-receipts"])
app.include_router(sales_order_router.router, prefix="/api/sales-orders", tags=["sales-orders"])
app.include_router(delivery_order_router.router, prefix="/api/delivery-orders", tags=["delivery-orders"])
app.include_router(invoice_router.router, prefix="/api/invoices", tags=["invoices"])
app.include_router(credit_note_router.router, prefix="/api/credit-notes", tags=["credit-notes"])
app.include_router(stock_transfer_router.router, prefix="/api/stock-transfers", tags=["stock-transfers"])
app.include_router(stock_adjustment_router.router, prefix="/api/stock-adjustments", tags=["stock-adjustments"])
app.include_router(inventory_router.router, prefix="/api/inventory", tags=["inventory"])
app.include_router(ai_router.router, prefix="/api/ai", tags=["ai"])


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"], include_in_schema=False)
async def health() -> dict[str, Any]:
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    redis_ok = await ping_redis()

    return {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "demo_mode": settings.DEMO_MODE,
        "checks": {
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }
