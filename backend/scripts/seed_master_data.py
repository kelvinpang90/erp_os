#!/usr/bin/env python3
"""
Seed script: create the minimal master data required for a fresh demo environment.

Creates (idempotently):
  1. Organization   — Demo Malaysia Sdn Bhd (org_id=1)
  2. Permissions    — ~30 codes across all modules
  3. Roles          — Admin / Manager / Sales / Purchaser + permission assignments
  4. Users          — 4 demo accounts (passwords per CLAUDE.md Part 13)
  5. Warehouses     — KL / Penang / Johor Bahru

Run inside the container:
  docker compose exec backend python scripts/seed_master_data.py

Idempotent: safe to re-run; existing records are skipped.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure the package root is importable when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.enums import RoleCode, WarehouseType
from app.models.organization import Organization, Permission, Role, RolePermission, User, UserRole, Warehouse

log = structlog.get_logger()

# ── Permission definitions ────────────────────────────────────────────────────
# Format: (code, module, action, description)

PERMISSIONS: list[tuple[str, str, str, str]] = [
    # Dashboard
    ("dashboard.view",     "dashboard",  "view",   "View dashboard and KPIs"),
    # SKU / Inventory
    ("sku.read",           "sku",        "read",   "View SKUs"),
    ("sku.create",         "sku",        "create", "Create SKUs"),
    ("sku.update",         "sku",        "update", "Update SKUs"),
    ("sku.delete",         "sku",        "delete", "Delete SKUs"),
    ("stock.read",         "stock",      "read",   "View stock levels and movements"),
    ("stock.adjust",       "stock",      "adjust", "Create stock adjustments"),
    ("stock.transfer",     "stock",      "transfer", "Create stock transfers"),
    # Purchase
    ("po.read",            "purchase",   "read",   "View purchase orders"),
    ("po.create",          "purchase",   "create", "Create purchase orders"),
    ("po.update",          "purchase",   "update", "Update purchase orders"),
    ("po.confirm",         "purchase",   "confirm","Confirm purchase orders"),
    ("po.cancel",          "purchase",   "cancel", "Cancel purchase orders (Manager+)"),
    ("gr.read",            "purchase",   "gr_read","View goods receipts"),
    ("gr.create",          "purchase",   "gr_create", "Create goods receipts"),
    ("supplier.read",      "supplier",   "read",   "View suppliers"),
    ("supplier.create",    "supplier",   "create", "Create suppliers"),
    ("supplier.update",    "supplier",   "update", "Update suppliers"),
    # Sales
    ("so.read",            "sales",      "read",   "View sales orders"),
    ("so.create",          "sales",      "create", "Create sales orders"),
    ("so.update",          "sales",      "update", "Update sales orders"),
    ("so.confirm",         "sales",      "confirm","Confirm sales orders"),
    ("so.cancel",          "sales",      "cancel", "Cancel sales orders"),
    ("do.read",            "sales",      "do_read","View delivery orders"),
    ("do.create",          "sales",      "do_create", "Create delivery orders"),
    ("customer.read",      "customer",   "read",   "View customers"),
    ("customer.create",    "customer",   "create", "Create customers"),
    ("customer.update",    "customer",   "update", "Update customers"),
    # e-Invoice
    ("einvoice.read",      "einvoice",   "read",   "View e-Invoices"),
    ("einvoice.create",    "einvoice",   "create", "Create e-Invoice drafts"),
    ("einvoice.submit",    "einvoice",   "submit", "Submit e-Invoices to MyInvois"),
    ("einvoice.reject",    "einvoice",   "reject", "Reject e-Invoices as buyer"),
    ("cn.read",            "einvoice",   "cn_read","View credit notes"),
    ("cn.create",          "einvoice",   "cn_create", "Create credit notes"),
    # Reports
    ("report.view",        "report",     "view",   "View reports and charts"),
    # Settings / Admin
    ("settings.view",      "settings",   "view",   "View settings"),
    ("settings.update",    "settings",   "update", "Update settings"),
    ("user.manage",        "user",       "manage", "Manage users and roles"),
    ("admin.demo_reset",   "admin",      "demo_reset", "Trigger demo data reset"),
    ("admin.dev_tools",    "admin",      "dev_tools",  "Access developer tools"),
]

# ── Role → permission assignments ─────────────────────────────────────────────

_ALL_PERMS = {p[0] for p in PERMISSIONS}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    RoleCode.ADMIN.value: _ALL_PERMS,

    RoleCode.MANAGER.value: _ALL_PERMS - {
        "user.manage",
        "admin.demo_reset",
        "admin.dev_tools",
    },

    RoleCode.SALES.value: {
        "dashboard.view",
        "sku.read",
        "stock.read",
        "so.read", "so.create", "so.update", "so.confirm", "so.cancel",
        "do.read", "do.create",
        "customer.read", "customer.create", "customer.update",
        "einvoice.read", "einvoice.create", "einvoice.submit", "einvoice.reject",
        "cn.read", "cn.create",
        "report.view",
    },

    RoleCode.PURCHASER.value: {
        "dashboard.view",
        "sku.read",
        "stock.read", "stock.adjust", "stock.transfer",
        "po.read", "po.create", "po.update", "po.confirm", "po.cancel",
        "gr.read", "gr.create",
        "supplier.read", "supplier.create", "supplier.update",
    },
}

# ── Demo users ────────────────────────────────────────────────────────────────

DEMO_USERS: list[dict] = [
    {
        "email": "admin@demo.my",
        "password": "Admin@123",
        "full_name": "Admin User",
        "role": RoleCode.ADMIN.value,
        "default_home": "/dashboard",
    },
    {
        "email": "manager@demo.my",
        "password": "Manager@123",
        "full_name": "Manager User",
        "role": RoleCode.MANAGER.value,
        "default_home": "/dashboard",
    },
    {
        "email": "sales@demo.my",
        "password": "Sales@123",
        "full_name": "Sales User",
        "role": RoleCode.SALES.value,
        "default_home": "/sales/orders",
    },
    {
        "email": "purchaser@demo.my",
        "password": "Purchaser@123",
        "full_name": "Purchaser User",
        "role": RoleCode.PURCHASER.value,
        "default_home": "/purchase/orders",
    },
]

# ── Warehouses ────────────────────────────────────────────────────────────────

WAREHOUSES: list[dict] = [
    {
        "code": "WH-KL",
        "name": "Main Warehouse - Kuala Lumpur",
        "type": WarehouseType.MAIN,
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50480",
    },
    {
        "code": "WH-PG",
        "name": "Branch - Penang",
        "type": WarehouseType.BRANCH,
        "city": "Georgetown",
        "state": "Pulau Pinang",
        "postcode": "10050",
    },
    {
        "code": "WH-JB",
        "name": "Branch - Johor Bahru",
        "type": WarehouseType.BRANCH,
        "city": "Johor Bahru",
        "state": "Johor",
        "postcode": "80000",
    },
]


# ── Seed functions ────────────────────────────────────────────────────────────

async def _get_or_create_org(session: AsyncSession) -> Organization:
    result = await session.execute(select(Organization).where(Organization.id == 1))
    org = result.scalar_one_or_none()
    if org:
        log.info("org_exists", org_id=1)
        return org

    org = Organization(
        code="DEMO",
        name="Demo Malaysia Sdn Bhd",
        registration_no="202001012345",
        tin="C2584563200",
        sst_registration_no="W10-1234-56789012",
        msic_code="46510",
        default_currency="MYR",
        address_line1="Lot 5, Jalan Teknologi 3/9",
        address_line2="Taman Sains Selangor",
        city="Petaling Jaya",
        state="Selangor",
        postcode="47810",
        country="MY",
        phone="+60 3-7803 8000",
        email="info@demo.my",
        ai_master_enabled=True,
        ai_features={
            "OCR_INVOICE": True,
            "EINVOICE_PRECHECK": True,
            "DASHBOARD_SUMMARY": True,
        },
    )
    session.add(org)
    await session.flush()
    log.info("org_created", org_id=org.id, name=org.name)
    return org


async def _seed_permissions(session: AsyncSession) -> dict[str, Permission]:
    """Upsert all permissions. Returns {code: Permission}."""
    result = await session.execute(select(Permission))
    existing = {p.code: p for p in result.scalars().all()}

    created = 0
    for code, module, action, description in PERMISSIONS:
        if code not in existing:
            perm = Permission(
                code=code,
                module=module,
                action=action,
                description=description,
            )
            session.add(perm)
            existing[code] = perm
            created += 1

    await session.flush()
    log.info("permissions_seeded", total=len(existing), created=created)
    return existing


async def _seed_roles(
    session: AsyncSession,
    org: Organization,
    perm_map: dict[str, Permission],
) -> dict[str, Role]:
    """Upsert roles and their permission assignments."""
    result = await session.execute(
        select(Role).where(Role.organization_id == org.id)
    )
    existing_roles = {r.code: r for r in result.scalars().all()}

    role_definitions = [
        (RoleCode.ADMIN.value,     "Administrator", "/dashboard"),
        (RoleCode.MANAGER.value,   "Manager",       "/dashboard"),
        (RoleCode.SALES.value,     "Sales",         "/sales/orders"),
        (RoleCode.PURCHASER.value, "Purchaser",     "/purchase/orders"),
    ]

    role_map: dict[str, Role] = {}
    for code, name, home in role_definitions:
        if code in existing_roles:
            role_map[code] = existing_roles[code]
            log.info("role_exists", code=code)
            continue

        role = Role(
            organization_id=org.id,
            code=code,
            name=name,
            default_home=home,
            is_system=True,
            is_active=True,
        )
        session.add(role)
        await session.flush()
        role_map[code] = role
        log.info("role_created", code=code, role_id=role.id)

    # Assign permissions
    for role_code, perm_codes in ROLE_PERMISSIONS.items():
        role = role_map.get(role_code)
        if role is None:
            continue

        # Get existing assignments
        existing_rp = await session.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        )
        existing_perm_ids = {rp.permission_id for rp in existing_rp.scalars().all()}

        added = 0
        for perm_code in perm_codes:
            perm = perm_map.get(perm_code)
            if perm is None or perm.id in existing_perm_ids:
                continue
            rp = RolePermission(role_id=role.id, permission_id=perm.id)
            session.add(rp)
            added += 1

        if added:
            await session.flush()
            log.info("permissions_assigned", role=role_code, added=added)

    return role_map


async def _seed_users(
    session: AsyncSession,
    org: Organization,
    role_map: dict[str, Role],
) -> None:
    """Upsert demo users and their role assignments."""
    for user_def in DEMO_USERS:
        result = await session.execute(
            select(User).where(
                User.organization_id == org.id,
                User.email == user_def["email"],
            )
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                organization_id=org.id,
                email=user_def["email"],
                password_hash=hash_password(user_def["password"]),
                full_name=user_def["full_name"],
                locale="en-US",
                theme="light",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            log.info("user_created", email=user_def["email"], user_id=user.id)
        else:
            log.info("user_exists", email=user_def["email"])

        # Assign role if not already assigned
        role = role_map.get(user_def["role"])
        if role is None:
            continue

        existing_ur = await session.execute(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == role.id,
            )
        )
        if existing_ur.scalar_one_or_none() is None:
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.flush()
            log.info("role_assigned", email=user_def["email"], role=user_def["role"])


async def _seed_warehouses(
    session: AsyncSession,
    org: Organization,
) -> None:
    """Upsert demo warehouses."""
    for wh_def in WAREHOUSES:
        result = await session.execute(
            select(Warehouse).where(
                Warehouse.organization_id == org.id,
                Warehouse.code == wh_def["code"],
            )
        )
        if result.scalar_one_or_none() is not None:
            log.info("warehouse_exists", code=wh_def["code"])
            continue

        wh = Warehouse(
            organization_id=org.id,
            code=wh_def["code"],
            name=wh_def["name"],
            type=wh_def["type"],
            city=wh_def.get("city"),
            state=wh_def.get("state"),
            postcode=wh_def.get("postcode"),
            country="MY",
            is_active=True,
        )
        session.add(wh)
        log.info("warehouse_created", code=wh_def["code"], name=wh_def["name"])

    await session.flush()


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    import logging
    logging.basicConfig(level=logging.INFO)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        async with session.begin():
            org = await _get_or_create_org(session)
            perm_map = await _seed_permissions(session)
            role_map = await _seed_roles(session, org, perm_map)
            await _seed_users(session, org, role_map)
            await _seed_warehouses(session, org)

    await engine.dispose()
    log.info("seed_complete", message="Master data seeded successfully.")
    print("\n✅ Seed complete — master data is ready.")


if __name__ == "__main__":
    asyncio.run(main())
