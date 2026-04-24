"""
Custom exception hierarchy for ERP OS.

All exceptions inherit from AppException. Global exception handlers in main.py
convert these into uniform JSON responses. Routers MUST raise these exceptions
instead of fastapi.HTTPException.
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base exception for all application errors."""

    http_status: int = 500
    default_error_code: str = "INTERNAL_ERROR"
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        error_code: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.error_code = error_code or self.default_error_code
        self.detail = detail
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"error_code={self.error_code!r}, "
            f"message={self.message!r})"
        )


class AuthenticationError(AppException):
    """401 — Token missing / expired / invalid, or credentials wrong."""

    http_status = 401
    default_error_code = "AUTHENTICATION_REQUIRED"
    default_message = "Authentication is required."


class AuthorizationError(AppException):
    """403 — Authenticated but lacks permission."""

    http_status = 403
    default_error_code = "PERMISSION_DENIED"
    default_message = "You do not have permission to perform this action."


class NotFoundError(AppException):
    """404 — Resource not found."""

    http_status = 404
    default_error_code = "NOT_FOUND"
    default_message = "The requested resource was not found."


class ConflictError(AppException):
    """409 — Duplicate / unique constraint violation."""

    http_status = 409
    default_error_code = "CONFLICT"
    default_message = "A conflict occurred with existing data."


class BusinessRuleError(AppException):
    """422 — Business rule violation (state machine, insufficient stock, etc.)."""

    http_status = 422
    default_error_code = "BUSINESS_RULE_VIOLATION"
    default_message = "The operation violates a business rule."


class ValidationError(AppException):
    """422 — Input validation failed (beyond Pydantic's built-in)."""

    http_status = 422
    default_error_code = "VALIDATION_ERROR"
    default_message = "Input validation failed."


class RateLimitError(AppException):
    """429 — Too many requests."""

    http_status = 429
    default_error_code = "RATE_LIMIT_EXCEEDED"
    default_message = "Too many requests. Please try again later."


class InternalError(AppException):
    """500 — Unexpected server error (wraps unknown exceptions)."""

    http_status = 500
    default_error_code = "INTERNAL_ERROR"
    default_message = "An unexpected error occurred."


# ── Convenience sub-classes for common scenarios ──────────────────────────────

class InvalidCredentialsError(AuthenticationError):
    default_error_code = "INVALID_CREDENTIALS"
    default_message = "Email or password is incorrect."


class TokenExpiredError(AuthenticationError):
    default_error_code = "TOKEN_EXPIRED"
    default_message = "Your session has expired. Please log in again."


class TokenInvalidError(AuthenticationError):
    default_error_code = "TOKEN_INVALID"
    default_message = "The provided token is invalid."


class AccountLockedError(AuthenticationError):
    default_error_code = "ACCOUNT_LOCKED"
    default_message = "Your account has been temporarily locked due to too many failed login attempts."


class TooManyAttemptsError(AuthenticationError):
    default_error_code = "TOO_MANY_ATTEMPTS"
    default_message = "Too many failed login attempts. Your account has been locked for 5 minutes."


class InsufficientStockError(BusinessRuleError):
    default_error_code = "INSUFFICIENT_STOCK"
    default_message = "Insufficient stock available for this operation."


class InvalidStatusTransitionError(BusinessRuleError):
    default_error_code = "INVALID_STATUS_TRANSITION"
    default_message = "This status transition is not allowed."
