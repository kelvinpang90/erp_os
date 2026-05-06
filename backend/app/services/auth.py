"""
AuthService — authentication and session management business logic.

Responsibilities:
  - login  : verify credentials, enforce lockout, issue tokens
  - refresh: rotate refresh token, issue new pair
  - logout : revoke refresh token
  - get_me : assemble user profile + permissions + menu tree
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
    TooManyAttemptsError,
    TokenInvalidError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    revoke_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.enums import RoleCode
from app.models.organization import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.user import AISettingsSnapshot, MeResponse, MenuNode, UserResponse

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()

# ── Constants ─────────────────────────────────────────────────────────────────

_MAX_FAILED_ATTEMPTS = 5        # attempts before lockout
_ATTEMPT_WINDOW_MINUTES = 5     # window to count failures
_LOCK_DURATION_MINUTES = 5      # how long to lock the account

# ── Menu definitions ──────────────────────────────────────────────────────────
# Each entry: (key, path, icon, label_i18n_key, required_role_codes)
# If required_role_codes is empty → visible to all authenticated users.

_MENU_DEFINITIONS: list[dict] = [
    {
        "key": "dashboard",
        "path": "/dashboard",
        "icon": "DashboardOutlined",
        "label": "menu.dashboard",
        "roles": [],  # all roles
        "children": [],
    },
    {
        "key": "purchase",
        "path": "/purchase",
        "icon": "ShoppingCartOutlined",
        "label": "menu.purchase",
        "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER],
        "children": [
            {
                "key": "purchase.orders",
                "path": "/purchase/orders",
                "icon": "",
                "label": "menu.purchase.orders",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER],
                "children": [],
            },
            {
                "key": "purchase.receipts",
                "path": "/purchase/receipts",
                "icon": "",
                "label": "menu.purchase.receipts",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER],
                "children": [],
            },
            {
                "key": "purchase.ocr",
                "path": "/purchase/ocr",
                "icon": "",
                "label": "menu.purchase.ocr",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER],
                "children": [],
            },
            {
                "key": "suppliers",
                "path": "/purchase/suppliers",
                "icon": "",
                "label": "menu.suppliers",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER],
                "children": [],
            },
        ],
    },
    {
        "key": "sales",
        "path": "/sales",
        "icon": "ShopOutlined",
        "label": "menu.sales",
        "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES],
        "children": [
            {
                "key": "sales.orders",
                "path": "/sales/orders",
                "icon": "",
                "label": "menu.sales.orders",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES],
                "children": [],
            },
            {
                "key": "sales.delivery",
                "path": "/sales/delivery",
                "icon": "",
                "label": "menu.sales.delivery",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES],
                "children": [],
            },
            {
                "key": "customers",
                "path": "/sales/customers",
                "icon": "",
                "label": "menu.customers",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES],
                "children": [],
            },
        ],
    },
    {
        "key": "einvoice",
        "path": "/einvoice",
        "icon": "FileTextOutlined",
        "label": "menu.einvoice",
        "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES],
        "children": [
            {
                "key": "einvoice.list",
                "path": "/einvoice/list",
                "icon": "",
                "label": "menu.einvoice.list",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES],
                "children": [],
            },
            {
                "key": "einvoice.credit-notes",
                "path": "/einvoice/credit-notes",
                "icon": "",
                "label": "menu.einvoice.credit_notes",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES],
                "children": [],
            },
            {
                "key": "einvoice.consolidated",
                "path": "/einvoice/consolidated",
                "icon": "",
                "label": "menu.einvoice.consolidated",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER],
                "children": [],
            },
        ],
    },
    {
        "key": "inventory",
        "path": "/inventory",
        "icon": "InboxOutlined",
        "label": "menu.inventory",
        "roles": [],  # all roles
        "children": [
            {
                "key": "inventory.skus",
                "path": "/inventory/skus",
                "icon": "",
                "label": "menu.inventory.skus",
                "roles": [],
                "children": [],
            },
            {
                "key": "inventory.stock",
                "path": "/inventory/stock",
                "icon": "",
                "label": "menu.inventory.stock",
                "roles": [],
                "children": [],
            },
            {
                "key": "inventory.movements",
                "path": "/inventory/movements",
                "icon": "",
                "label": "menu.inventory.movements",
                "roles": [],
                "children": [],
            },
            {
                "key": "inventory.transfers",
                "path": "/inventory/transfers",
                "icon": "",
                "label": "menu.inventory.transfers",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER],
                "children": [],
            },
            {
                "key": "inventory.adjustments",
                "path": "/inventory/adjustments",
                "icon": "",
                "label": "menu.inventory.adjustments",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER],
                "children": [],
            },
            {
                "key": "inventory.branch-matrix",
                "path": "/inventory/branch-matrix",
                "icon": "",
                "label": "menu.inventory.branch_matrix",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER],
                "children": [],
            },
            {
                "key": "inventory.alerts",
                "path": "/inventory/alerts",
                "icon": "",
                "label": "menu.inventory.alerts",
                "roles": [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER],
                "children": [],
            },
        ],
    },
    {
        "key": "reports",
        "path": "/reports",
        "icon": "BarChartOutlined",
        "label": "menu.reports",
        "roles": [RoleCode.ADMIN, RoleCode.MANAGER],
        "children": [],
    },
    {
        "key": "settings",
        "path": "/settings",
        "icon": "SettingOutlined",
        "label": "menu.settings",
        "roles": [RoleCode.ADMIN],
        "children": [
            {
                "key": "settings.general",
                "path": "/settings/general",
                "icon": "",
                "label": "menu.settings.general",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
            {
                "key": "settings.currencies",
                "path": "/settings/currencies",
                "icon": "",
                "label": "menu.settings.currencies",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
            {
                "key": "settings.tax-rates",
                "path": "/settings/tax-rates",
                "icon": "",
                "label": "menu.settings.tax_rates",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
            {
                "key": "settings.ai",
                "path": "/settings/ai",
                "icon": "",
                "label": "menu.settings.ai",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
            {
                "key": "settings.users",
                "path": "/settings/users",
                "icon": "",
                "label": "menu.settings.users",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
            {
                "key": "settings.warehouses",
                "path": "/settings/warehouses",
                "icon": "",
                "label": "menu.settings.warehouses",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
            {
                "key": "settings.uoms",
                "path": "/settings/uoms",
                "icon": "",
                "label": "menu.settings.uoms",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
            {
                "key": "settings.brands",
                "path": "/settings/brands",
                "icon": "",
                "label": "menu.settings.brands",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
            {
                "key": "settings.categories",
                "path": "/settings/categories",
                "icon": "",
                "label": "menu.settings.categories",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
        ],
    },
    {
        "key": "admin",
        "path": "/admin",
        "icon": "ToolOutlined",
        "label": "menu.admin",
        "roles": [RoleCode.ADMIN],
        "children": [
            {
                "key": "admin.dev-tools",
                "path": "/admin/dev-tools",
                "icon": "",
                "label": "menu.admin.dev_tools",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
            {
                "key": "admin.demo-reset",
                "path": "/admin/demo-reset",
                "icon": "",
                "label": "menu.admin.demo_reset",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
            {
                "key": "admin.audit-logs",
                "path": "/admin/audit-logs",
                "icon": "",
                "label": "menu.admin.audit_logs",
                "roles": [RoleCode.ADMIN],
                "children": [],
            },
        ],
    },
]


def _build_menu_for_roles(role_codes: list[str]) -> list[MenuNode]:
    """Filter _MENU_DEFINITIONS to only nodes visible to the given role codes."""
    role_set = {RoleCode(r) for r in role_codes if r in RoleCode.__members__}

    def _node_visible(node: dict) -> bool:
        required: list[RoleCode] = node.get("roles", [])
        if not required:
            return True  # open to all
        return bool(role_set & set(required))

    def _build(nodes: list[dict]) -> list[MenuNode]:
        result: list[MenuNode] = []
        for node in nodes:
            if not _node_visible(node):
                continue
            children = _build(node.get("children", []))
            result.append(
                MenuNode(
                    key=node["key"],
                    path=node["path"],
                    icon=node.get("icon", ""),
                    label=node["label"],
                    children=children,
                )
            )
        return result

    return _build(_MENU_DEFINITIONS)


# ── AuthService ───────────────────────────────────────────────────────────────

class AuthService:
    """Stateless service; instantiate per-request with session + redis."""

    def __init__(self, session: AsyncSession, redis_auth: Redis) -> None:
        self.session = session
        self.redis_auth = redis_auth
        self.user_repo = UserRepository(session)

    # ── login ─────────────────────────────────────────────────────────────────

    async def login(
        self,
        email: str,
        password: str,
        org_id: int = 1,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """
        Authenticate a user and return a token pair.

        Steps:
          1. Lookup user — if not found, constant-time delay to prevent timing attacks
          2. Check account lock
          3. Check recent failed attempts → lock if ≥ threshold
          4. Verify password
          5. Record attempt, update last_login, issue tokens
        """
        log = logger.bind(email=email, ip=ip_address)

        user = await self.user_repo.get_by_email(org_id, email)

        if user is None:
            # Constant-time: simulate bcrypt verify to prevent timing enumeration
            await asyncio.sleep(0.3)
            await self.user_repo.record_login_attempt(
                email=email,
                success=False,
                org_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            log.warning("login_failed", reason="user_not_found")
            raise InvalidCredentialsError()

        # Check account lock
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        if user.locked_until and user.locked_until > now_naive:
            log.warning("login_blocked", reason="account_locked")
            raise AccountLockedError()

        # Count recent failures
        recent_failures = await self.user_repo.count_recent_failed_attempts(
            email=email,
            within_minutes=_ATTEMPT_WINDOW_MINUTES,
        )
        if recent_failures >= _MAX_FAILED_ATTEMPTS:
            lock_until = now_naive + timedelta(minutes=_LOCK_DURATION_MINUTES)
            await self.user_repo.set_locked_until(user, lock_until)
            await self.user_repo.record_login_attempt(
                email=email,
                success=False,
                org_id=user.organization_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            log.warning("login_blocked", reason="too_many_attempts", failures=recent_failures)
            raise TooManyAttemptsError()

        # Verify password
        if not verify_password(password, user.password_hash):
            await self.user_repo.record_login_attempt(
                email=email,
                success=False,
                org_id=user.organization_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            log.warning("login_failed", reason="wrong_password")
            raise InvalidCredentialsError()

        # Success
        await self.user_repo.record_login_attempt(
            email=email,
            success=True,
            org_id=user.organization_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.user_repo.update_last_login(user, ip_address)

        # Load roles for token payload (get_by_email does not eagerly load them)
        user_with_roles = await self.user_repo.get_with_roles_permissions(user.id)
        role_codes = [r.code for r in user_with_roles.roles] if (user_with_roles and user_with_roles.roles) else []
        access_token = create_access_token(
            user_id=user.id,
            org_id=user.organization_id,
            role_codes=role_codes,
        )
        refresh_token = await create_refresh_token(
            user_id=user.id,
            org_id=user.organization_id,
            redis_auth=self.redis_auth,
        )

        log.info("login_success", user_id=user.id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ── refresh ───────────────────────────────────────────────────────────────

    async def refresh(self, token_id: str) -> TokenResponse:
        """
        Rotate the refresh token and return a new token pair.

        Old token is revoked immediately (one-time-use, prevents replay).
        """
        payload = await verify_refresh_token(token_id, self.redis_auth)
        await revoke_refresh_token(token_id, self.redis_auth)

        user = await self.user_repo.get_with_roles_permissions(payload["user_id"])
        if user is None or not user.is_active:
            raise TokenInvalidError(message="User account is no longer active.")

        role_codes = [r.code for r in user.roles] if user.roles else []
        access_token = create_access_token(
            user_id=user.id,
            org_id=user.organization_id,
            role_codes=role_codes,
        )
        new_refresh = await create_refresh_token(
            user_id=user.id,
            org_id=user.organization_id,
            redis_auth=self.redis_auth,
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ── logout ────────────────────────────────────────────────────────────────

    async def logout(self, token_id: str) -> None:
        """Revoke the refresh token. Idempotent — ignores missing tokens."""
        await revoke_refresh_token(token_id, self.redis_auth)

    # ── get_me ────────────────────────────────────────────────────────────────

    async def get_me(self, user: User) -> MeResponse:
        """
        Build the full /me response.

        Loads roles + permissions via selectinload if not already loaded.
        """
        # Ensure roles and permissions are loaded
        user_with_roles = await self.user_repo.get_with_roles_permissions(user.id)
        if user_with_roles is None:
            raise TokenInvalidError()

        # Collect permission codes (de-duplicated)
        permission_codes: set[str] = set()
        role_codes: list[str] = []
        for role in user_with_roles.roles:
            role_codes.append(role.code)
            for perm in role.permissions:
                permission_codes.add(perm.code)

        menu = _build_menu_for_roles(role_codes)

        # Inline imports avoid a top-level cycle on settings ↔ services.
        from app.core.config import settings as app_settings
        from app.models.organization import Organization

        org = await self.session.get(Organization, user_with_roles.organization_id)
        master_enabled = bool(org and org.ai_master_enabled and app_settings.AI_ENABLED)
        features_raw = dict((org.ai_features if org else None) or {})
        # Always surface the documented feature keys with default ON so the UI
        # toggles render predictably even before the org has saved settings.
        for key in ("OCR_INVOICE", "EINVOICE_PRECHECK", "DASHBOARD_SUMMARY"):
            features_raw.setdefault(key, True)
        features = {k: bool(v) for k, v in features_raw.items()}
        ai_settings = AISettingsSnapshot(
            master_enabled=master_enabled,
            features=features,
        )

        return MeResponse(
            user=UserResponse.model_validate(user_with_roles),
            permissions=sorted(permission_codes),
            menu=menu,
            demo_mode=app_settings.DEMO_MODE,
            ai_settings=ai_settings,
        )
