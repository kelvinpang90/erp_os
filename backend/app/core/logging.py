"""
Structured logging configuration using structlog.

Features:
- JSON output in production, colored console output in development
- request_id propagated via contextvars throughout the request lifecycle
- RequestIDMiddleware injects a UUID4 request_id and echoes it in X-Request-ID header
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings

# ── Context variables for per-request metadata ───────────────────────────────

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
client_ip_var: ContextVar[str] = ContextVar("client_ip", default="")
user_agent_var: ContextVar[str] = ContextVar("user_agent", default="")


def get_request_id() -> str:
    return request_id_var.get()


def get_client_ip() -> str:
    return client_ip_var.get()


def get_user_agent() -> str:
    return user_agent_var.get()


# ── structlog processor: inject request_id into every log record ──────────────

def _add_request_id(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    rid = get_request_id()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


# ── Main configuration ────────────────────────────────────────────────────────

def configure_logging() -> None:
    """Call once at application startup (inside lifespan)."""
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        _add_request_id,
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.ENVIRONMENT == "production":
        # JSON — machine-readable, sent to log aggregator
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        # Pretty console output for local dev
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(
        logging.DEBUG if settings.DEBUG else logging.INFO
    )

    # Silence noisy third-party loggers
    for name in ("uvicorn.access", "sqlalchemy.engine", "aiomysql"):
        logging.getLogger(name).setLevel(logging.WARNING)


# ── Middleware ────────────────────────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Generates a UUID4 request_id for every incoming request.

    - Stores it in the request_id_var ContextVar so structlog picks it up.
    - Echoes it back in the X-Request-ID response header.
    - Accepts X-Request-ID from the caller (useful for tracing across services).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Use caller-provided ID if present, otherwise generate new one
        incoming = request.headers.get("X-Request-ID")
        rid = incoming if incoming else str(uuid.uuid4())

        client_ip = request.client.host if request.client else ""
        user_agent = request.headers.get("user-agent", "")[:500]

        rid_token = request_id_var.set(rid)
        ip_token = client_ip_var.set(client_ip)
        ua_token = user_agent_var.set(user_agent)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(rid_token)
            client_ip_var.reset(ip_token)
            user_agent_var.reset(ua_token)

        response.headers["X-Request-ID"] = rid
        return response
