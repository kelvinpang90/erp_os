from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.master import Category
from app.models.organization import User
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.common import PaginatedResponse, PaginationParams


def _build_path(parent_path: str | None, parent_id: int | None, code: str) -> str:
    if parent_path and parent_id:
        return f"{parent_path}/{code}"
    return code


async def list_categories(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    user: User,
    parent_id: int | None = None,
    is_active: bool | None = None,
) -> PaginatedResponse[CategoryResponse]:
    repo = CategoryRepository(session)
    filters = [
        Category.organization_id == user.organization_id,
        Category.deleted_at.is_(None),
    ]
    if parent_id is not None:
        filters.append(Category.parent_id == parent_id)
    if is_active is not None:
        filters.append(Category.is_active == is_active)

    items, total = await repo.list_all(
        filters=filters,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse.build(
        items=[CategoryResponse.model_validate(c) for c in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_category(
    session: AsyncSession,
    category_id: int,
    *,
    user: User,
) -> CategoryResponse:
    repo = CategoryRepository(session)
    cat = await repo.get_by_id(category_id)
    if not cat or cat.organization_id != user.organization_id or cat.deleted_at is not None:
        raise NotFoundError(message=f"Category {category_id} not found.")
    return CategoryResponse.model_validate(cat)


async def create_category(
    session: AsyncSession,
    data: CategoryCreate,
    *,
    user: User,
) -> CategoryResponse:
    repo = CategoryRepository(session)
    existing = await repo.get_by_code(user.organization_id, data.code)
    if existing:
        raise ConflictError(message=f"Category with code '{data.code}' already exists.")

    parent_path: str | None = None
    if data.parent_id is not None:
        parent = await repo.get_by_id(data.parent_id)
        if not parent or parent.organization_id != user.organization_id or parent.deleted_at is not None:
            raise NotFoundError(message=f"Parent category {data.parent_id} not found.")
        parent_path = parent.path

    path = _build_path(parent_path, data.parent_id, data.code)
    cat = await repo.create(
        organization_id=user.organization_id,
        code=data.code,
        name=data.name,
        name_zh=data.name_zh,
        parent_id=data.parent_id,
        path=path,
    )
    return CategoryResponse.model_validate(cat)


async def update_category(
    session: AsyncSession,
    category_id: int,
    data: CategoryUpdate,
    *,
    user: User,
) -> CategoryResponse:
    repo = CategoryRepository(session)
    cat = await repo.get_by_id(category_id)
    if not cat or cat.organization_id != user.organization_id or cat.deleted_at is not None:
        raise NotFoundError(message=f"Category {category_id} not found.")

    if data.code is not None and data.code != cat.code:
        existing = await repo.get_by_code(user.organization_id, data.code)
        if existing:
            raise ConflictError(message=f"Category with code '{data.code}' already exists.")

    if data.parent_id is not None and data.parent_id == category_id:
        raise BusinessRuleError(message="Category cannot be its own parent.")

    updates = data.model_dump(exclude_unset=True)
    cat = await repo.update(cat, **updates)
    return CategoryResponse.model_validate(cat)


async def delete_category(
    session: AsyncSession,
    category_id: int,
    *,
    user: User,
) -> None:
    repo = CategoryRepository(session)
    cat = await repo.get_by_id(category_id)
    if not cat or cat.organization_id != user.organization_id or cat.deleted_at is not None:
        raise NotFoundError(message=f"Category {category_id} not found.")

    children = await repo.get_children(user.organization_id, category_id)
    if children:
        raise BusinessRuleError(
            message="Cannot delete a category that has sub-categories. Remove children first."
        )

    await repo.soft_delete(cat)
