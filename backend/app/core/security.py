"""
Security utilities: password hashing (bcrypt) and JWT token management.

Access token  — HS256 JWT, short-lived (15 min), stateless.
Refresh token — UUID4, stored in Redis (DB 2) with TTL, one-time-use (rotated on refresh).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt
from redis.asyncio import Redis

from app.core.config import settings
from app.core.exceptions import TokenExpiredError, TokenInvalidError

# ── Constants ─────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
_RT_PREFIX = "rt:"          # Redis key prefix for refresh tokens


# ── Pydantic-free payload dataclass ──────────────────────────────────────────

class TokenPayload:
    """Decoded access token payload."""

    __slots__ = ("user_id", "org_id", "role_codes", "exp")

    def __init__(
        self,
        user_id: int,
        org_id: int,
        role_codes: list[str],
        exp: datetime,
    ) -> None:
        self.user_id = user_id
        self.org_id = org_id
        self.role_codes = role_codes
        self.exp = exp


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt (cost = settings.BCRYPT_ROUNDS)."""
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*. Constant-time comparison."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── Access token (JWT) ────────────────────────────────────────────────────────

def create_access_token(
    user_id: int,
    org_id: int,
    role_codes: list[str],
) -> str:
    """Create a signed HS256 JWT valid for ACCESS_TOKEN_EXPIRE_MINUTES minutes."""
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": org_id,
        "roles": role_codes,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT access token.

    Raises:
        TokenExpiredError: Token has passed its exp timestamp.
        TokenInvalidError: Token signature / structure is invalid.
    """
    try:
        raw: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise TokenInvalidError()

    try:
        return TokenPayload(
            user_id=int(raw["sub"]),
            org_id=int(raw["org"]),
            role_codes=list(raw.get("roles", [])),
            exp=datetime.fromtimestamp(raw["exp"], tz=UTC),
        )
    except (KeyError, ValueError, TypeError):
        raise TokenInvalidError()


# ── Refresh token (UUID4 + Redis) ─────────────────────────────────────────────

async def create_refresh_token(
    user_id: int,
    org_id: int,
    redis_auth: Redis,
) -> str:
    """
    Generate a UUID4 refresh token and store its payload in Redis (DB 2).

    Key  : rt:{token_id}
    Value: JSON {"user_id": ..., "org_id": ...}
    TTL  : REFRESH_TOKEN_EXPIRE_DAYS days
    """
    token_id = str(uuid.uuid4())
    value = json.dumps({"user_id": user_id, "org_id": org_id})
    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400
    await redis_auth.setex(_RT_PREFIX + token_id, ttl_seconds, value)
    return token_id


async def verify_refresh_token(
    token_id: str,
    redis_auth: Redis,
) -> dict[str, int]:
    """
    Verify a refresh token exists in Redis and return its payload.

    Returns:
        dict with keys "user_id" and "org_id"

    Raises:
        TokenInvalidError: Token not found (expired or never existed).
    """
    raw = await redis_auth.get(_RT_PREFIX + token_id)
    if raw is None:
        raise TokenInvalidError(
            message="Refresh token is invalid or has expired.",
            error_code="REFRESH_TOKEN_INVALID",
        )
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, TypeError):
        raise TokenInvalidError()


async def revoke_refresh_token(token_id: str, redis_auth: Redis) -> None:
    """Delete a refresh token from Redis (logout / rotation)."""
    await redis_auth.delete(_RT_PREFIX + token_id)
