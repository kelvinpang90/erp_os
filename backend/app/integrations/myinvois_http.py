"""HTTP transport for LHDN MyInvois.

Owns everything network-shaped so :mod:`app.integrations.myinvois_real` can
stay a thin translation between our DTOs and LHDN's JSON:

- OAuth 2.0 client-credentials handshake against ``/connect/token``
- access-token caching in Redis, shared across uvicorn workers and Celery
- bounded retry with exponential backoff on 429 / 5xx
- mapping of transport and HTTP failures onto ``MyInvoisError``

Environment base URLs are derived from ``MYINVOIS_MODE`` rather than read from
env, so a preprod credential can never be pointed at production by editing a
single variable.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx
import structlog

from app.core.exceptions import ConfigurationError, MyInvoisError
from app.core.redis import redis_cache

logger = structlog.get_logger()


# ── Environments ─────────────────────────────────────────────────────────────

_ENVIRONMENTS: dict[str, dict[str, str]] = {
    "sandbox": {
        "api": "https://preprod-api.myinvois.hasil.gov.my",
        "portal": "https://preprod.myinvois.hasil.gov.my",
    },
    "production": {
        "api": "https://api.myinvois.hasil.gov.my",
        "portal": "https://myinvois.hasil.gov.my",
    },
}

TOKEN_PATH = "/connect/token"
SUBMIT_PATH = "/api/v1.0/documentsubmissions"
DOCUMENT_DETAILS_PATH = "/api/v1.0/documents/{uuid}/details"
DOCUMENT_STATE_PATH = "/api/v1.0/documents/state/{uuid}/state"

_SCOPE = "InvoicingAPI"
# Renew this many seconds before LHDN's stated expiry so an in-flight request
# never races the cutover.
_TOKEN_SKEW_SECONDS = 60
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


def environment_urls(mode: str) -> dict[str, str]:
    """Return the API and portal base URLs for a mode."""
    try:
        return _ENVIRONMENTS[mode]
    except KeyError:
        raise ConfigurationError(
            message=f"MYINVOIS_MODE={mode!r} has no HTTP environment.",
            error_code="MYINVOIS_UNKNOWN_MODE",
        ) from None


class MyInvoisHttpClient:
    """Authenticated JSON client for the MyInvois REST API."""

    def __init__(
        self,
        *,
        mode: str,
        client_id: str,
        client_secret: str,
        on_behalf_of: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not client_id or not client_secret:
            raise ConfigurationError(
                message=(
                    f"MYINVOIS_MODE={mode!r} requires MYINVOIS_CLIENT_ID and "
                    "MYINVOIS_CLIENT_SECRET to be set."
                ),
                error_code="MYINVOIS_MISSING_CREDENTIALS",
            )
        urls = environment_urls(mode)
        self.mode = mode
        self.api_base_url = urls["api"]
        self.portal_base_url = urls["portal"]
        self._client_id = client_id
        self._client_secret = client_secret
        self._on_behalf_of = on_behalf_of
        self._max_retries = max_retries
        self._token_key = f"myinvois:token:{mode}:{client_id}"
        # Separate connect and read budgets: LHDN validation can be slow to
        # respond, but a dead host should fail fast.
        self._timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self._transport: Optional[httpx.AsyncBaseTransport] = None
        # Guards the token refresh within one process; Redis handles the
        # cross-process case (a duplicate refresh there is harmless).
        self._token_lock = asyncio.Lock()

    # ── Test seam ────────────────────────────────────────────────────────────

    def set_transport(self, transport: httpx.AsyncBaseTransport) -> None:
        """Inject an ``httpx`` transport so tests can run fully offline."""
        self._transport = transport

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.api_base_url,
            timeout=self._timeout,
            transport=self._transport,
        )

    # ── Auth ─────────────────────────────────────────────────────────────────

    async def _cached_token(self) -> Optional[str]:
        try:
            return await redis_cache.get(self._token_key)
        except Exception as exc:  # pragma: no cover - cache is best-effort
            logger.warning("myinvois_token_cache_read_failed", error=str(exc))
            return None

    async def _store_token(self, token: str, expires_in: int) -> None:
        ttl = max(int(expires_in) - _TOKEN_SKEW_SECONDS, 1)
        try:
            await redis_cache.setex(self._token_key, ttl, token)
        except Exception as exc:  # pragma: no cover - cache is best-effort
            logger.warning("myinvois_token_cache_write_failed", error=str(exc))

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        """Return a valid access token, minting a new one only when needed."""
        if not force_refresh:
            cached = await self._cached_token()
            if cached:
                return cached

        async with self._token_lock:
            if not force_refresh:
                cached = await self._cached_token()
                if cached:
                    return cached

            form = {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
                "scope": _SCOPE,
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            if self._on_behalf_of:
                headers["onbehalfof"] = self._on_behalf_of

            response = await self._send(
                "POST", TOKEN_PATH, data=form, headers=headers, authenticated=False
            )
            body = _json_body(response)
            token = body.get("access_token")
            if not token:
                raise MyInvoisError(
                    message="MyInvois token response did not include an access_token.",
                    error_code="MYINVOIS_TOKEN_INVALID",
                    detail={"body": body},
                )
            await self._store_token(token, int(body.get("expires_in", 3600)))
            logger.info("myinvois_token_issued", mode=self.mode)
            return str(token)

    # ── Requests ─────────────────────────────────────────────────────────────

    async def _send(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        data: Any = None,
        headers: Optional[dict[str, str]] = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        """Send one request, retrying transient failures with backoff."""
        request_headers = dict(headers or {})
        if authenticated:
            token = await self.get_access_token()
            request_headers["Authorization"] = f"Bearer {token}"
            if self._on_behalf_of:
                request_headers["onbehalfof"] = self._on_behalf_of

        last_error: Optional[Exception] = None
        async with self._new_client() as client:
            for attempt in range(self._max_retries):
                try:
                    response = await client.request(
                        method, path, json=json, data=data, headers=request_headers
                    )
                except httpx.HTTPError as exc:
                    last_error = exc
                    logger.warning(
                        "myinvois_request_transport_error",
                        path=path,
                        attempt=attempt + 1,
                        error=str(exc),
                    )
                else:
                    if response.status_code not in _RETRY_STATUSES:
                        return response
                    last_error = MyInvoisError(
                        message=f"MyInvois returned HTTP {response.status_code}.",
                        detail=_safe_detail(response),
                    )
                    logger.warning(
                        "myinvois_request_retryable_status",
                        path=path,
                        attempt=attempt + 1,
                        status=response.status_code,
                    )

                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2**attempt)

        if isinstance(last_error, MyInvoisError):
            raise last_error
        raise MyInvoisError(
            message="Could not reach LHDN MyInvois.",
            detail={"path": path, "error": str(last_error)},
        ) from last_error

    async def post_json(self, path: str, payload: Any) -> dict[str, Any]:
        response = await self._send(
            "POST", path, json=payload, headers={"Content-Type": "application/json"}
        )
        _raise_for_status(response, path)
        return _json_body(response)

    async def put_json(self, path: str, payload: Any) -> dict[str, Any]:
        response = await self._send(
            "PUT", path, json=payload, headers={"Content-Type": "application/json"}
        )
        _raise_for_status(response, path)
        return _json_body(response)

    async def get_json(self, path: str) -> dict[str, Any]:
        response = await self._send("GET", path)
        _raise_for_status(response, path)
        return _json_body(response)


# ── Response helpers ─────────────────────────────────────────────────────────


def _json_body(response: httpx.Response) -> dict[str, Any]:
    if not response.content:
        return {}
    try:
        body = response.json()
    except ValueError as exc:
        raise MyInvoisError(
            message="MyInvois returned a non-JSON response.",
            error_code="MYINVOIS_BAD_RESPONSE",
            detail={"status": response.status_code, "body": response.text[:500]},
        ) from exc
    return body if isinstance(body, dict) else {"data": body}


def _safe_detail(response: httpx.Response) -> dict[str, Any]:
    """Best-effort error detail that never raises while building it."""
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text[:500]
    return {"status": response.status_code, "body": body}


def _raise_for_status(response: httpx.Response, path: str) -> None:
    if response.is_success:
        return
    detail = _safe_detail(response)
    detail["path"] = path
    if response.status_code in (401, 403):
        raise MyInvoisError(
            message="MyInvois rejected our credentials.",
            error_code="MYINVOIS_UNAUTHORIZED",
            detail=detail,
        )
    raise MyInvoisError(
        message=f"MyInvois returned HTTP {response.status_code}.",
        error_code="MYINVOIS_HTTP_ERROR",
        detail=detail,
    )
