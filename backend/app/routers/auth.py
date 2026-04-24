"""
Authentication router — /api/auth/*

Endpoints:
  POST /login    — issue token pair (rate-limited: 10/min per IP)
  POST /refresh  — rotate refresh token
  POST /logout   — revoke refresh token
  GET  /me       — current user profile + permissions + menu

No business logic here; all delegated to AuthService.
"""

# NOTE: Do NOT add `from __future__ import annotations` here.
# It converts all type annotations to strings (ForwardRef), which breaks
# FastAPI's Body() parameter resolution when combined with slowapi decorators.

from fastapi import APIRouter, Body, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.redis import redis_auth
from app.models.organization import User
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse
from app.schemas.user import MeResponse
from app.services.auth import AuthService

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ── Helper ────────────────────────────────────────────────────────────────────

def _service(db: AsyncSession) -> AuthService:
    return AuthService(session=db, redis_auth=redis_auth)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, summary="Login with email + password")
@limiter.limit("10/minute")
async def login(
    request: Request,
    credentials: LoginRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate with email and password.

    - Rate-limited to 10 requests per minute per IP.
    - Returns access_token (15 min) + refresh_token (7 days, one-time-use).
    - 5 failed attempts in 5 minutes → account locked for 5 minutes.
    """
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    return await _service(db).login(
        email=credentials.email,
        password=credentials.password,
        ip_address=ip,
        user_agent=ua,
    )


@router.post("/refresh", response_model=TokenResponse, summary="Rotate refresh token")
@limiter.limit("20/minute")
async def refresh_token(
    request: Request,
    payload: RefreshRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new token pair.

    The old refresh token is immediately revoked (one-time-use).
    """
    return await _service(db).refresh(payload.refresh_token)


@router.post("/logout", response_model=dict, summary="Revoke refresh token")
async def logout(
    payload: LogoutRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Revoke the provided refresh token.
    Idempotent — calling with an already-revoked token is not an error.
    """
    await _service(db).logout(payload.refresh_token)
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=MeResponse, summary="Current user profile")
async def me(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MeResponse:
    """
    Return the authenticated user's profile, permission list, and menu tree.

    The frontend uses this to render navigation and enforce UI-level access control.
    """
    return await _service(db).get_me(user)
