"""
Generic BaseRepository[T] providing standard CRUD operations.

All concrete repositories inherit from this class and only add
domain-specific query methods. The Service layer calls repositories;
repositories MUST NOT contain business logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async repository backed by SQLAlchemy 2.0."""

    def __init__(self, model: Type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_id(self, record_id: int) -> ModelT | None:
        """Return a single record by primary key, or None."""
        return await self.session.get(self.model, record_id)

    async def get_by_ids(self, ids: list[int]) -> list[ModelT]:
        """Return all records whose PK is in *ids*, preserving no order guarantee."""
        if not ids:
            return []
        stmt = select(self.model).where(self.model.id.in_(ids))  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(
        self,
        *,
        filters: list[Any] | None = None,
        order_by: list[Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ModelT], int]:
        """
        Return (items, total_count) with optional filtering and ordering.

        Applies soft-delete filter automatically when the model has deleted_at.
        """
        stmt = select(self.model)
        count_stmt = select(func.count()).select_from(self.model)

        # Soft-delete guard
        if hasattr(self.model, "deleted_at"):
            soft_del_filter = self.model.deleted_at.is_(None)  # type: ignore[attr-defined]
            stmt = stmt.where(soft_del_filter)
            count_stmt = count_stmt.where(soft_del_filter)

        if filters:
            for f in filters:
                stmt = stmt.where(f)
                count_stmt = count_stmt.where(f)

        if order_by:
            stmt = stmt.order_by(*order_by)

        stmt = stmt.limit(limit).offset(offset)

        total_result = await self.session.execute(count_stmt)
        total: int = total_result.scalar_one()

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, **kwargs: Any) -> ModelT:
        """Instantiate, add to session, and flush (but not commit)."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelT, **kwargs: Any) -> ModelT:
        """Apply keyword updates to *instance*, flush, and return it."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, instance: ModelT) -> ModelT:
        """
        Mark *instance* as deleted by setting deleted_at and is_active.

        Raises AttributeError if the model does not support soft delete.
        """
        if not hasattr(instance, "deleted_at"):
            raise AttributeError(
                f"{self.model.__name__} does not support soft delete."
            )
        instance.deleted_at = datetime.now(UTC).replace(tzinfo=None)  # type: ignore[attr-defined]
        instance.is_active = False  # type: ignore[attr-defined]
        self.session.add(instance)
        await self.session.flush()
        return instance
