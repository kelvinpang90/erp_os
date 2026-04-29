"""add unique index on invoices.sales_order_id (Window 11)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-29 02:00:00.000000

Window 11 enforces 1 SalesOrder ↔ 1 Invoice. A unique index on
``sales_order_id`` (NULL values not constrained, courtesy of MySQL's
behaviour for indexed nullable columns) prevents duplicate invoice
generation for the same SO and gives the service layer a hard backstop
even if the idempotency check is bypassed.

Stand-alone consolidated invoices (sales_order_id IS NULL) are not
affected.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the non-unique helper index added by the initial schema before
    # creating the unique one (MySQL allows multiple indexes on the same
    # column but having both is wasteful).
    op.drop_index("ix_inv_so", table_name="invoices")
    op.create_index(
        "uq_inv_so",
        "invoices",
        ["organization_id", "sales_order_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_inv_so", table_name="invoices")
    op.create_index("ix_inv_so", "invoices", ["sales_order_id"], unique=False)
