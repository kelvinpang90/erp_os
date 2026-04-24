"""
Common Pydantic schemas reused across the application.

- PaginationParams  — query parameters for paginated list endpoints
- PaginatedResponse — generic paginated response wrapper
- ErrorResponse     — unified error body returned by global exception handlers
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for list endpoints. Inject via Depends(PaginationParams)."""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of records per page (max 100)",
    )

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int = Field(description="Total number of records matching the filter")
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def build(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        import math

        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if page_size else 1,
        )


class ErrorResponse(BaseModel):
    """Unified error response body. Never expose internal stack traces."""

    error_code: str = Field(description="Machine-readable error code (UPPER_SNAKE_CASE)")
    message: str = Field(description="Human-readable error message")
    request_id: str = Field(description="UUID4 request identifier for tracing")
    timestamp: datetime = Field(description="UTC timestamp of the error")
    detail: dict | None = Field(default=None, description="Optional structured detail")
