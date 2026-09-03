"""Unit tests for the real MyInvois adapter and its HTTP transport.

Fully offline — every request is served by an ``httpx.MockTransport``, and the
Redis token cache is stubbed. Covers:

  1. Token handshake — form fields, caching, forced refresh, onbehalfof
  2. Retry — 429/5xx backoff, 4xx fail-fast, transport errors
  3. Document encoding — minified hash/base64 agreement, size ceiling
  4. submit — accepted → validated, pending → validated_at None, rejections
  5. get_status — status mapping, QR link construction
  6. reject — request shape
  7. Factory — mode selection and configuration guards
"""

from __future__ import annotations

import base64
import hashlib
import json
from decimal import Decimal
from typing import Any, Optional

import httpx
import pytest

from app.core.exceptions import (
    ConfigurationError,
    MyInvoisError,
    MyInvoisRejectedError,
)
from app.integrations.myinvois import InvoicePayload
from app.integrations.myinvois_http import MyInvoisHttpClient, environment_urls
from app.integrations.myinvois_real import MyInvoisRealAdapter, encode_document


# ── Test doubles ─────────────────────────────────────────────────────────────


class FakeTokenCache:
    """Stands in for Redis; the client only uses get/setex."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value
        self.ttls[key] = ttl


class Recorder:
    """Scripted MockTransport handler that records every request."""

    def __init__(self, routes: dict[str, Any]) -> None:
        # route key: "METHOD /path" (path prefix match), value: Response or list
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = f"{request.method} {request.url.path}"
        for route, response in self.routes.items():
            if key.startswith(route):
                if isinstance(response, list):
                    # Pop through the script, repeating the last entry.
                    return response.pop(0) if len(response) > 1 else response[0]
                return response
        return httpx.Response(404, json={"error": f"unrouted {key}"})

    def find(self, method: str, path_fragment: str) -> list[httpx.Request]:
        return [
            r
            for r in self.requests
            if r.method == method and path_fragment in r.url.path
        ]


def _token_response(expires_in: int = 3600) -> httpx.Response:
    return httpx.Response(
        200, json={"access_token": "tok-abc", "expires_in": expires_in}
    )


@pytest.fixture
def cache(monkeypatch) -> FakeTokenCache:
    fake = FakeTokenCache()
    monkeypatch.setattr("app.integrations.myinvois_http.redis_cache", fake)
    return fake


def make_client(
    recorder: Recorder,
    *,
    mode: str = "sandbox",
    on_behalf_of: Optional[str] = None,
    max_retries: int = 3,
) -> MyInvoisHttpClient:
    client = MyInvoisHttpClient(
        mode=mode,
        client_id="cid",
        client_secret="secret",
        on_behalf_of=on_behalf_of,
        max_retries=max_retries,
    )
    client.set_transport(httpx.MockTransport(recorder))
    return client


def make_payload(**overrides) -> InvoicePayload:
    base = dict(
        document_no="INV-2026-00042",
        invoice_type="INVOICE",
        business_date="2026-09-01",
        currency="MYR",
        exchange_rate=Decimal("1"),
        seller_tin="C1234567890",
        seller_name="Demo Malaysia Sdn Bhd",
        seller_msic_code="46510",
        seller_sst_no=None,
        buyer_tin="C9876543210",
        buyer_name="Penang Retail Sdn Bhd",
        buyer_msic_code=None,
        subtotal_excl_tax=Decimal("1000.00"),
        tax_amount=Decimal("100.00"),
        total_incl_tax=Decimal("1100.00"),
        line_count=0,
        issue_time="08:30:00Z",
    )
    base.update(overrides)
    return InvoicePayload(**base)


def _submit_accepted(uuid: str = "UUID123") -> httpx.Response:
    return httpx.Response(
        202,
        json={
            "submissionUid": "SUB123",
            "acceptedDocuments": [{"uuid": uuid, "invoiceCodeNumber": "INV-2026-00042"}],
            "rejectedDocuments": [],
        },
    )


def _details(status: str, **extra: Any) -> httpx.Response:
    body: dict[str, Any] = {"uuid": "UUID123", "status": status}
    body.update(extra)
    return httpx.Response(200, json=body)


# ── 1. Token handshake ───────────────────────────────────────────────────────


class TestToken:
    @pytest.mark.asyncio
    async def test_form_fields_and_caching(self, cache):
        recorder = Recorder({"POST /connect/token": _token_response()})
        client = make_client(recorder)

        assert await client.get_access_token() == "tok-abc"
        # Second call is served from cache — still exactly one network hit.
        assert await client.get_access_token() == "tok-abc"
        assert len(recorder.find("POST", "/connect/token")) == 1

        body = recorder.requests[0].content.decode()
        assert "grant_type=client_credentials" in body
        assert "scope=InvoicingAPI" in body
        assert "client_id=cid" in body
        assert "client_secret=secret" in body

    @pytest.mark.asyncio
    async def test_cache_ttl_leaves_renewal_headroom(self, cache):
        recorder = Recorder({"POST /connect/token": _token_response(expires_in=3600)})
        client = make_client(recorder)
        await client.get_access_token()
        assert list(cache.ttls.values()) == [3540]

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, cache):
        recorder = Recorder({"POST /connect/token": _token_response()})
        client = make_client(recorder)
        await client.get_access_token()
        await client.get_access_token(force_refresh=True)
        assert len(recorder.find("POST", "/connect/token")) == 2

    @pytest.mark.asyncio
    async def test_missing_access_token_raises(self, cache):
        recorder = Recorder({"POST /connect/token": httpx.Response(200, json={})})
        client = make_client(recorder)
        with pytest.raises(MyInvoisError) as exc:
            await client.get_access_token()
        assert exc.value.error_code == "MYINVOIS_TOKEN_INVALID"

    @pytest.mark.asyncio
    async def test_bearer_token_and_onbehalfof_on_api_calls(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "GET /api/v1.0/documents": _details("Valid"),
            }
        )
        client = make_client(recorder, on_behalf_of="C555")
        await client.get_json("/api/v1.0/documents/UUID123/details")

        api_request = recorder.find("GET", "/documents")[0]
        assert api_request.headers["Authorization"] == "Bearer tok-abc"
        assert api_request.headers["onbehalfof"] == "C555"
        # The token request carries it too, for intermediary onboarding.
        assert recorder.requests[0].headers["onbehalfof"] == "C555"

    @pytest.mark.asyncio
    async def test_cache_failure_degrades_to_a_fresh_token(self, monkeypatch):
        class BrokenCache:
            async def get(self, key):
                raise RuntimeError("redis down")

            async def setex(self, key, ttl, value):
                raise RuntimeError("redis down")

        monkeypatch.setattr(
            "app.integrations.myinvois_http.redis_cache", BrokenCache()
        )
        recorder = Recorder({"POST /connect/token": _token_response()})
        client = make_client(recorder)
        assert await client.get_access_token() == "tok-abc"


# ── 2. Retry and error mapping ───────────────────────────────────────────────


class TestRetry:
    @pytest.fixture(autouse=True)
    def _no_sleep(self, monkeypatch):
        async def instant(_seconds):
            return None

        monkeypatch.setattr("app.integrations.myinvois_http.asyncio.sleep", instant)

    @pytest.mark.asyncio
    async def test_retries_429_then_succeeds(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "GET /api/v1.0/documents": [
                    httpx.Response(429, json={"error": "slow down"}),
                    _details("Valid"),
                ],
            }
        )
        client = make_client(recorder)
        body = await client.get_json("/api/v1.0/documents/UUID123/details")
        assert body["status"] == "Valid"
        assert len(recorder.find("GET", "/documents")) == 2

    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "GET /api/v1.0/documents": httpx.Response(503, json={"error": "down"}),
            }
        )
        client = make_client(recorder, max_retries=3)
        with pytest.raises(MyInvoisError):
            await client.get_json("/api/v1.0/documents/UUID123/details")
        assert len(recorder.find("GET", "/documents")) == 3

    @pytest.mark.asyncio
    async def test_4xx_is_not_retried(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "GET /api/v1.0/documents": httpx.Response(400, json={"error": "bad"}),
            }
        )
        client = make_client(recorder)
        with pytest.raises(MyInvoisError) as exc:
            await client.get_json("/api/v1.0/documents/UUID123/details")
        assert exc.value.error_code == "MYINVOIS_HTTP_ERROR"
        assert len(recorder.find("GET", "/documents")) == 1

    @pytest.mark.asyncio
    async def test_401_maps_to_unauthorized(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "GET /api/v1.0/documents": httpx.Response(401, json={"error": "nope"}),
            }
        )
        client = make_client(recorder)
        with pytest.raises(MyInvoisError) as exc:
            await client.get_json("/api/v1.0/documents/UUID123/details")
        assert exc.value.error_code == "MYINVOIS_UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_transport_error_becomes_myinvois_error(self, cache):
        def explode(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/connect/token":
                return _token_response()
            raise httpx.ConnectError("no route to host")

        client = MyInvoisHttpClient(mode="sandbox", client_id="cid", client_secret="s")
        client.set_transport(httpx.MockTransport(explode))
        with pytest.raises(MyInvoisError):
            await client.get_json("/api/v1.0/documents/UUID123/details")

    @pytest.mark.asyncio
    async def test_non_json_response_is_reported_clearly(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "GET /api/v1.0/documents": httpx.Response(200, text="<html>oops</html>"),
            }
        )
        client = make_client(recorder)
        with pytest.raises(MyInvoisError) as exc:
            await client.get_json("/api/v1.0/documents/UUID123/details")
        assert exc.value.error_code == "MYINVOIS_BAD_RESPONSE"


# ── 3. Document encoding ─────────────────────────────────────────────────────


class TestEncodeDocument:
    def test_hash_matches_the_encoded_bytes(self):
        document = {"Invoice": [{"ID": [{"_": "INV-1"}]}]}
        encoded, digest = encode_document(document)
        raw = base64.b64decode(encoded)
        assert hashlib.sha256(raw).hexdigest() == digest
        assert json.loads(raw.decode("utf-8")) == document

    def test_document_is_minified(self):
        encoded, _ = encode_document({"a": 1, "b": 2})
        assert base64.b64decode(encoded).decode() == '{"a":1,"b":2}'

    def test_oversized_document_is_rejected(self):
        oversized = {"blob": "x" * (301 * 1024)}
        with pytest.raises(MyInvoisError) as exc:
            encode_document(oversized)
        assert exc.value.error_code == "MYINVOIS_DOCUMENT_TOO_LARGE"


# ── 4. Submit ────────────────────────────────────────────────────────────────


class TestSubmit:
    @pytest.fixture(autouse=True)
    def _no_sleep(self, monkeypatch):
        async def instant(_seconds):
            return None

        monkeypatch.setattr("app.integrations.myinvois_real.asyncio.sleep", instant)

    @pytest.mark.asyncio
    async def test_validated_in_one_pass(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "POST /api/v1.0/documentsubmissions": _submit_accepted(),
                "GET /api/v1.0/documents": _details(
                    "Valid",
                    longId="LONG999",
                    dateTimeValidated="2026-09-01T08:31:00Z",
                ),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        result = await adapter.submit(make_payload())

        assert result.uin == "UUID123"
        assert result.submission_uid == "SUB123"
        assert result.validated_at is not None
        assert result.validated_at.tzinfo is None          # naive UTC, rule A5
        assert result.validated_at.hour == 8 and result.validated_at.minute == 31
        assert (
            result.qr_code_url
            == "https://preprod.myinvois.hasil.gov.my/UUID123/share/LONG999"
        )

    @pytest.mark.asyncio
    async def test_submission_envelope_shape(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "POST /api/v1.0/documentsubmissions": _submit_accepted(),
                "GET /api/v1.0/documents": _details("Valid", longId="L1"),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        await adapter.submit(make_payload())

        body = json.loads(recorder.find("POST", "/documentsubmissions")[0].content)
        document = body["documents"][0]
        assert document["format"] == "JSON"
        assert document["codeNumber"] == "INV-2026-00042"
        raw = base64.b64decode(document["document"])
        assert hashlib.sha256(raw).hexdigest() == document["documentHash"]
        assert json.loads(raw)["Invoice"][0]["ID"][0]["_"] == "INV-2026-00042"

    @pytest.mark.asyncio
    async def test_pending_validation_returns_no_validated_at(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "POST /api/v1.0/documentsubmissions": _submit_accepted(),
                "GET /api/v1.0/documents": _details("Submitted"),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder), poll_attempts=3)
        result = await adapter.submit(make_payload())

        assert result.uin == "UUID123"
        assert result.validated_at is None
        assert result.qr_code_url is None
        # The poll budget was spent, and no re-submission was attempted.
        assert len(recorder.find("GET", "/documents")) == 3
        assert len(recorder.find("POST", "/documentsubmissions")) == 1

    @pytest.mark.asyncio
    async def test_stops_polling_once_settled(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "POST /api/v1.0/documentsubmissions": _submit_accepted(),
                "GET /api/v1.0/documents": [
                    _details("Submitted"),
                    _details("Valid", longId="L1", dateTimeValidated="2026-09-01T08:31:00Z"),
                ],
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder), poll_attempts=5)
        result = await adapter.submit(make_payload())
        assert result.validated_at is not None
        assert len(recorder.find("GET", "/documents")) == 2

    @pytest.mark.asyncio
    async def test_rejected_at_submission(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "POST /api/v1.0/documentsubmissions": httpx.Response(
                    202,
                    json={
                        "submissionUid": "SUB123",
                        "acceptedDocuments": [],
                        "rejectedDocuments": [
                            {
                                "invoiceCodeNumber": "INV-2026-00042",
                                "error": {"code": "DS302", "message": "Invalid TIN"},
                            }
                        ],
                    },
                ),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        with pytest.raises(MyInvoisRejectedError) as exc:
            await adapter.submit(make_payload())
        assert exc.value.error_code == "MYINVOIS_REJECTED"
        assert exc.value.detail["rejectedDocuments"][0]["error"]["code"] == "DS302"

    @pytest.mark.asyncio
    async def test_invalid_after_validation_raises_with_reason(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "POST /api/v1.0/documentsubmissions": _submit_accepted(),
                "GET /api/v1.0/documents": _details(
                    "Invalid",
                    validationResults={
                        "status": "Invalid",
                        "validationSteps": [
                            {"name": "Step-TIN", "status": "Valid"},
                            {"name": "Step-Signature", "status": "Invalid"},
                        ],
                    },
                ),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        with pytest.raises(MyInvoisRejectedError) as exc:
            await adapter.submit(make_payload())
        assert "Step-Signature" in exc.value.message

    @pytest.mark.asyncio
    async def test_empty_submission_result_raises(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "POST /api/v1.0/documentsubmissions": httpx.Response(
                    202, json={"submissionUid": "SUB123"}
                ),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        with pytest.raises(MyInvoisError) as exc:
            await adapter.submit(make_payload())
        assert exc.value.error_code == "MYINVOIS_EMPTY_SUBMISSION_RESULT"

    @pytest.mark.asyncio
    async def test_accepts_uppercase_submission_uid_spelling(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "POST /api/v1.0/documentsubmissions": httpx.Response(
                    202,
                    json={
                        "submissionUID": "SUB-UPPER",
                        "acceptedDocuments": [{"uuid": "UUID123"}],
                    },
                ),
                "GET /api/v1.0/documents": _details("Valid", longId="L1"),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        result = await adapter.submit(make_payload())
        assert result.submission_uid == "SUB-UPPER"


# ── 5. Status ────────────────────────────────────────────────────────────────


class TestGetStatus:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "lhdn_status,expected",
        [
            ("Submitted", "SUBMITTED"),
            ("Valid", "VALIDATED"),
            ("Invalid", "REJECTED"),
            ("Cancelled", "REJECTED"),
        ],
    )
    async def test_status_mapping(self, cache, lhdn_status, expected):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "GET /api/v1.0/documents": _details(lhdn_status),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        result = await adapter.get_status("UUID123")
        assert result.status == expected

    @pytest.mark.asyncio
    async def test_unknown_status_raises(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "GET /api/v1.0/documents": _details("Teleported"),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        with pytest.raises(MyInvoisError) as exc:
            await adapter.get_status("UUID123")
        assert exc.value.error_code == "MYINVOIS_UNKNOWN_STATUS"

    @pytest.mark.asyncio
    async def test_rejected_carries_reason_and_qr(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "GET /api/v1.0/documents": _details(
                    "Invalid",
                    longId="L1",
                    validationResults={
                        "validationSteps": [{"name": "Step-TIN", "status": "Invalid"}]
                    },
                ),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        result = await adapter.get_status("UUID123")
        assert "Step-TIN" in result.rejection_reason
        assert result.qr_code_url.endswith("/UUID123/share/L1")


# ── 6. Reject ────────────────────────────────────────────────────────────────


class TestReject:
    @pytest.mark.asyncio
    async def test_request_shape(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "PUT /api/v1.0/documents/state": httpx.Response(
                    200, json={"uuid": "UUID123", "status": "Requested for Rejection"}
                ),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        result = await adapter.reject("UUID123", reason="Wrong quantity")

        assert result.success is True
        request = recorder.find("PUT", "/documents/state")[0]
        assert request.url.path == "/api/v1.0/documents/state/UUID123/state"
        assert json.loads(request.content) == {
            "status": "Rejected",
            "reason": "Wrong quantity",
        }

    @pytest.mark.asyncio
    async def test_expired_window_surfaces_the_lhdn_error(self, cache):
        recorder = Recorder(
            {
                "POST /connect/token": _token_response(),
                "PUT /api/v1.0/documents/state": httpx.Response(
                    400, json={"error": {"code": "OperationPeriodOver"}}
                ),
            }
        )
        adapter = MyInvoisRealAdapter(make_client(recorder))
        with pytest.raises(MyInvoisError) as exc:
            await adapter.reject("UUID123", reason="too late")
        assert exc.value.detail["body"]["error"]["code"] == "OperationPeriodOver"


# ── 7. Environments and factory ──────────────────────────────────────────────


class TestEnvironmentAndFactory:
    def test_environment_urls(self):
        assert environment_urls("sandbox") == {
            "api": "https://preprod-api.myinvois.hasil.gov.my",
            "portal": "https://preprod.myinvois.hasil.gov.my",
        }
        assert environment_urls("production") == {
            "api": "https://api.myinvois.hasil.gov.my",
            "portal": "https://myinvois.hasil.gov.my",
        }

    def test_unknown_mode_rejected(self):
        with pytest.raises(ConfigurationError):
            environment_urls("staging")

    def test_missing_credentials_rejected(self):
        with pytest.raises(ConfigurationError) as exc:
            MyInvoisHttpClient(mode="sandbox", client_id="", client_secret="")
        assert exc.value.error_code == "MYINVOIS_MISSING_CREDENTIALS"

    def test_factory_returns_mock_by_default(self, monkeypatch):
        from app.integrations import myinvois_factory
        from app.integrations.myinvois_mock import MyInvoisMockAdapter

        monkeypatch.setattr(
            myinvois_factory.settings, "MYINVOIS_MODE", "mock", raising=False
        )
        myinvois_factory.reset_adapter_cache()
        try:
            assert isinstance(myinvois_factory.get_myinvois_adapter(), MyInvoisMockAdapter)
        finally:
            myinvois_factory.reset_adapter_cache()

    def test_factory_builds_real_adapter_for_sandbox(self, monkeypatch):
        from app.integrations import myinvois_factory

        monkeypatch.setattr(
            myinvois_factory.settings, "MYINVOIS_MODE", "sandbox", raising=False
        )
        monkeypatch.setattr(
            myinvois_factory.settings, "MYINVOIS_CLIENT_ID", "cid", raising=False
        )
        monkeypatch.setattr(
            myinvois_factory.settings, "MYINVOIS_CLIENT_SECRET", "sec", raising=False
        )
        myinvois_factory.reset_adapter_cache()
        try:
            adapter = myinvois_factory.get_myinvois_adapter()
            assert isinstance(adapter, MyInvoisRealAdapter)
        finally:
            myinvois_factory.reset_adapter_cache()

    def test_factory_refuses_sandbox_without_credentials(self, monkeypatch):
        from app.integrations import myinvois_factory

        monkeypatch.setattr(
            myinvois_factory.settings, "MYINVOIS_MODE", "sandbox", raising=False
        )
        monkeypatch.setattr(
            myinvois_factory.settings, "MYINVOIS_CLIENT_ID", "", raising=False
        )
        myinvois_factory.reset_adapter_cache()
        try:
            with pytest.raises(ConfigurationError):
                myinvois_factory.get_myinvois_adapter()
        finally:
            myinvois_factory.reset_adapter_cache()

    def test_factory_refuses_when_signing_requested(self, monkeypatch):
        """Signing is unimplemented — fail loudly rather than send unsigned."""
        from app.integrations import myinvois_factory

        monkeypatch.setattr(
            myinvois_factory.settings, "MYINVOIS_MODE", "sandbox", raising=False
        )
        monkeypatch.setattr(
            myinvois_factory.settings, "MYINVOIS_CLIENT_ID", "cid", raising=False
        )
        monkeypatch.setattr(
            myinvois_factory.settings, "MYINVOIS_CLIENT_SECRET", "sec", raising=False
        )
        monkeypatch.setattr(
            myinvois_factory.settings, "MYINVOIS_SIGN_ENABLED", True, raising=False
        )
        myinvois_factory.reset_adapter_cache()
        try:
            with pytest.raises(ConfigurationError) as exc:
                myinvois_factory.get_myinvois_adapter()
            assert exc.value.error_code == "MYINVOIS_SIGNING_UNAVAILABLE"
        finally:
            myinvois_factory.reset_adapter_cache()
