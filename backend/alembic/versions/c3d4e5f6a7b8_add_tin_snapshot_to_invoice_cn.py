"""add seller_tin / buyer_tin snapshot to invoices and credit_notes

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-04 22:00:00.000000

Window 11 missed snapshotting the buyer/seller TIN onto the invoice and
credit-note rows themselves. LHDN MyInvois requires TIN on every
submitted document, and CLAUDE.md C4 mandates that single-use legal
documents must snapshot key counterparty fields so future master-data
edits can't retroactively alter past records.

This migration adds two NULLable VARCHAR(16) columns to both ``invoices``
and ``credit_notes``: ``seller_tin`` (from ``organizations.tin``) and
``buyer_tin`` (from ``customers.tin``). Existing rows are backfilled
from the current related-entity TIN at upgrade time so historical demo
invoices remain consistent.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns
    op.add_column("invoices", sa.Column("seller_tin", sa.String(length=16), nullable=True))
    op.add_column("invoices", sa.Column("buyer_tin", sa.String(length=16), nullable=True))
    op.add_column("credit_notes", sa.Column("seller_tin", sa.String(length=16), nullable=True))
    op.add_column("credit_notes", sa.Column("buyer_tin", sa.String(length=16), nullable=True))

    # Backfill existing rows from current organization/customer TIN.
    # Keeps demo data sensible without forcing manual reseed.
    op.execute(
        """
        UPDATE invoices i
        JOIN organizations o ON o.id = i.organization_id
        SET i.seller_tin = o.tin
        WHERE i.seller_tin IS NULL AND o.tin IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE invoices i
        JOIN customers c ON c.id = i.customer_id
        SET i.buyer_tin = c.tin
        WHERE i.buyer_tin IS NULL AND c.tin IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE credit_notes cn
        JOIN organizations o ON o.id = cn.organization_id
        SET cn.seller_tin = o.tin
        WHERE cn.seller_tin IS NULL AND o.tin IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE credit_notes cn
        JOIN customers c ON c.id = cn.customer_id
        SET cn.buyer_tin = c.tin
        WHERE cn.buyer_tin IS NULL AND c.tin IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("credit_notes", "buyer_tin")
    op.drop_column("credit_notes", "seller_tin")
    op.drop_column("invoices", "buyer_tin")
    op.drop_column("invoices", "seller_tin")
