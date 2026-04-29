"""MyInvois adapter factory.

Selects the concrete adapter based on settings. Window 11 ships only the
mock implementation; sandbox / production stubs raise NotImplementedError
to make the remaining work explicit.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.integrations.myinvois import MyInvoisAdapter
from app.integrations.myinvois_mock import MyInvoisMockAdapter


@lru_cache
def get_myinvois_adapter() -> MyInvoisAdapter:
    mode = settings.MYINVOIS_MODE
    if mode == "mock":
        return MyInvoisMockAdapter()
    if mode == "sandbox":
        raise NotImplementedError(
            "MyInvois sandbox adapter is not yet implemented. "
            "See docs for activation steps (OAuth credentials, signing certificate)."
        )
    if mode == "production":
        raise NotImplementedError(
            "MyInvois production adapter is not yet implemented. "
            "Production rollout is gated on customer onboarding."
        )
    raise ValueError(f"Unknown MYINVOIS_MODE: {mode!r}")


def reset_adapter_cache() -> None:
    """Test hook to clear the cached adapter when settings change."""
    get_myinvois_adapter.cache_clear()
