"""The app really is wired to the UTC response class, on every route.

`test_utc_json.py` proves the class marks what it renders. That is not the same
as proving FastAPI uses it, and the gap between "the code is right" and "the
code is reachable" is exactly where the last three of these bugs lived. So this
asserts the wiring itself: every registered API route, not a sample, and one
request that goes through the stack and comes back off the wire.

It fails if somebody adds a router with a `response_class` of its own, which is
the one way a new endpoint could go back to shipping naive timestamps.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.core.json import UtcJSONResponse
from app.main import app


# Streaming routes cannot render through a JSON response class -- they are not
# one response. The OCR one is the only such route, and it carries no datetime:
# the single date-shaped field on its payload is `business_date`, a `date`
# (`schemas/ai.py:39`), which must stay unmarked anyway.
STREAMING_ROUTES = {"/api/ai/ocr/purchase-order"}


def test_every_api_route_renders_through_the_utc_response_class():
    """All of them. A sample would pass while the one that mattered did not."""
    offenders = [
        f"{route.path} ({route.response_class.__name__})"
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith("/api")
        and route.path not in STREAMING_ROUTES
        and route.response_class is not UtcJSONResponse
    ]
    assert offenders == [], (
        "these routes would still ship naive timestamps: " + ", ".join(offenders)
    )


def test_the_streaming_exceptions_are_still_only_the_ones_we_vetted():
    """Pinned deliberately. A new streaming endpoint is a decision -- does its
    payload carry a datetime? -- and this is what makes somebody take it rather
    than inherit an exemption written for a different route."""
    streaming = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith("/api")
        and route.response_class is not UtcJSONResponse
    }
    assert streaming == STREAMING_ROUTES


def test_there_are_actually_routes_to_check():
    """Guards the test above against passing because it found nothing."""
    api_routes = [
        route for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api")
    ]
    assert len(api_routes) > 50, f"only {len(api_routes)} API routes found"


def test_a_naive_timestamp_leaves_the_stack_marked():
    """End to end, off the wire, through the real app's response pipeline.

    The route is registered the same way every real one is, so it inherits the
    same default -- that is the thing being demonstrated.
    """
    probe = APIRouter()

    @probe.get("/api/_test/timestamps")
    async def _timestamps() -> dict:
        return {
            "created_at": "2026-09-12T08:49:20",
            "business_date": "2026-09-12",
            "note": "raised 2026-09-12T08:49:20 by WhatsApp",
        }

    app.include_router(probe)
    try:
        body = TestClient(app).get("/api/_test/timestamps").json()
    finally:
        # Leave the app as it was found; other tests share this module-level app.
        app.router.routes = [
            route for route in app.router.routes
            if getattr(route, "path", None) != "/api/_test/timestamps"
        ]

    assert body["created_at"] == "2026-09-12T08:49:20Z"
    # The two landmines, checked where it counts rather than only in isolation.
    assert body["business_date"] == "2026-09-12"
    assert body["note"] == "raised 2026-09-12T08:49:20 by WhatsApp"
