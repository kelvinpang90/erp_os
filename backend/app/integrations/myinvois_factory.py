"""MyInvois adapter factory.

Selects the concrete adapter from ``MYINVOIS_MODE``:

- ``mock``      — offline deterministic adapter (local dev, demo, tests)
- ``sandbox``   — LHDN preprod (https://preprod-api.myinvois.hasil.gov.my)
- ``production``— LHDN production (https://api.myinvois.hasil.gov.my)

Both live modes share one implementation; only the base URLs and credentials
differ. Misconfiguration raises ``ConfigurationError`` here, at construction,
rather than surfacing as a 500 on the first submission.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.integrations.myinvois import MyInvoisAdapter
from app.integrations.myinvois_http import MyInvoisHttpClient
from app.integrations.myinvois_mock import MyInvoisMockAdapter
from app.integrations.myinvois_real import MyInvoisRealAdapter


@lru_cache
def get_myinvois_adapter() -> MyInvoisAdapter:
    mode = settings.MYINVOIS_MODE
    if mode == "mock":
        return MyInvoisMockAdapter()
    if mode in ("sandbox", "production"):
        if settings.MYINVOIS_SIGN_ENABLED:
            # Guard rather than silently downgrade: someone who switched this on
            # is expecting v1.1 signed documents, and shipping unsigned ones
            # instead would be a compliance failure discovered far too late.
            raise ConfigurationError(
                message=(
                    "MYINVOIS_SIGN_ENABLED is on but XAdES signing is not "
                    "implemented — it requires an X.509 certificate from a "
                    "Malaysian licensed CA. Unset it to submit v1.0 documents "
                    "(signature validation disabled)."
                ),
                error_code="MYINVOIS_SIGNING_UNAVAILABLE",
            )
        client = MyInvoisHttpClient(
            mode=mode,
            client_id=settings.MYINVOIS_CLIENT_ID,
            client_secret=settings.MYINVOIS_CLIENT_SECRET,
            on_behalf_of=settings.MYINVOIS_ON_BEHALF_OF or None,
            timeout_seconds=settings.MYINVOIS_TIMEOUT_SECONDS,
        )
        return MyInvoisRealAdapter(
            client,
            poll_attempts=settings.MYINVOIS_POLL_ATTEMPTS,
            poll_interval_seconds=settings.MYINVOIS_POLL_INTERVAL_SECONDS,
        )
    raise ConfigurationError(
        message=f"Unknown MYINVOIS_MODE: {mode!r}",
        error_code="MYINVOIS_UNKNOWN_MODE",
    )


def reset_adapter_cache() -> None:
    """Test hook to clear the cached adapter when settings change."""
    get_myinvois_adapter.cache_clear()
