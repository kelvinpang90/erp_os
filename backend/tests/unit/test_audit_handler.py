"""Unit tests for the W17 audit handler.

The handler runs after-commit in a fresh AsyncSessionLocal session, so we
mock that context manager and assert the AuditLog row that gets persisted.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums import AuditAction
from app.events.handlers import audit as audit_handler
from app.events.types import (
    DocumentStatusChanged,
    EInvoiceValidated,
    StockMovementOccurred,
)


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _patched_session(session: AsyncMock):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return patch.object(audit_handler, "AsyncSessionLocal", return_value=cm)


@pytest.mark.asyncio
class TestAuditDocumentStatusChanged:
    async def test_po_confirm_persists_audit_row(self) -> None:
        session = _make_session()
        event = DocumentStatusChanged(
            document_type="PO",
            document_id=42,
            document_no="PO-2026-00042",
            old_status="DRAFT",
            new_status="CONFIRMED",
            organization_id=1,
            actor_user_id=7,
        )

        with _patched_session(session):
            await audit_handler.handle_document_status_changed(event)

        session.add.assert_called_once()
        session.commit.assert_called_once()

        row = session.add.call_args.args[0]
        assert row.entity_type == "PO"
        assert row.entity_id == 42
        assert row.action == AuditAction.APPROVED
        assert row.actor_user_id == 7
        assert row.before == {"status": "DRAFT", "document_no": "PO-2026-00042"}
        assert row.after == {"status": "CONFIRMED", "document_no": "PO-2026-00042"}

    async def test_so_cancel_records_cancelled_action(self) -> None:
        session = _make_session()
        event = DocumentStatusChanged(
            document_type="SO",
            document_id=99,
            document_no="SO-2026-00099",
            old_status="CONFIRMED",
            new_status="CANCELLED",
            organization_id=1,
            actor_user_id=3,
        )

        with _patched_session(session):
            await audit_handler.handle_document_status_changed(event)

        row = session.add.call_args.args[0]
        assert row.entity_type == "SO"
        assert row.action == AuditAction.CANCELLED
        assert row.before["status"] == "CONFIRMED"
        assert row.after["status"] == "CANCELLED"

    async def test_invoice_submit_action_mapping(self) -> None:
        session = _make_session()
        event = DocumentStatusChanged(
            document_type="INVOICE",
            document_id=15,
            document_no="INV-2026-00015",
            old_status="DRAFT",
            new_status="SUBMITTED",
            organization_id=1,
            actor_user_id=2,
        )

        with _patched_session(session):
            await audit_handler.handle_document_status_changed(event)

        row = session.add.call_args.args[0]
        assert row.action == AuditAction.SUBMITTED

    async def test_credit_note_cancel_with_extra_snapshot(self) -> None:
        session = _make_session()
        event = DocumentStatusChanged(
            document_type="CN",
            document_id=21,
            document_no="CN-2026-00021",
            old_status="DRAFT",
            new_status="CANCELLED",
            organization_id=1,
            actor_user_id=4,
            before={"total_incl_tax": "1000.00"},
            after={"total_incl_tax": "1000.00", "cancel_reason": "duplicate"},
        )

        with _patched_session(session):
            await audit_handler.handle_document_status_changed(event)

        row = session.add.call_args.args[0]
        assert row.before["total_incl_tax"] == "1000.00"
        assert row.after["cancel_reason"] == "duplicate"
        assert row.after["status"] == "CANCELLED"

    async def test_skips_synthetic_batch_event(self) -> None:
        """The lazy-finalize scan publishes a synthetic event with id=0."""
        session = _make_session()
        event = DocumentStatusChanged(
            document_type="INVOICE",
            document_id=0,
            document_no="<batch-finalize x5>",
            old_status="VALIDATED",
            new_status="FINAL",
            organization_id=1,
        )

        with _patched_session(session):
            await audit_handler.handle_document_status_changed(event)

        session.add.assert_not_called()
        session.commit.assert_not_called()


@pytest.mark.asyncio
class TestAuditEInvoiceValidated:
    async def test_persists_validated_audit_row(self) -> None:
        session = _make_session()
        event = EInvoiceValidated(
            organization_id=1,
            invoice_id=15,
            invoice_no="INV-2026-00015",
            uin="LHDN-UIN-XYZ",
            validated_at="2026-04-29T10:00:00Z",
        )

        with _patched_session(session):
            await audit_handler.handle_einvoice_validated(event)

        row = session.add.call_args.args[0]
        assert row.entity_type == "INVOICE"
        assert row.entity_id == 15
        assert row.action == AuditAction.VALIDATED
        assert row.after["uin"] == "LHDN-UIN-XYZ"


@pytest.mark.asyncio
class TestAuditStockMovement:
    async def test_logs_only_no_db_write(self) -> None:
        """Stock movements live in stock_movements table — handler is log-only."""
        session = _make_session()
        event = StockMovementOccurred(
            organization_id=1,
            sku_id=10,
            warehouse_id=20,
            movement_type="SALES_OUT",
            source_document_type="DO",
            source_document_id=99,
        )

        with _patched_session(session):
            await audit_handler.handle_stock_movement_occurred(event)

        session.add.assert_not_called()
        session.commit.assert_not_called()
