"""add avg_cost_after to goods_receipt_lines

Revision ID: a1b2c3d4e5f6
Revises: 8058342b33b7
Create Date: 2026-04-28 02:00:00.000000

Adds an avg_cost_after snapshot column to goods_receipt_lines so the UI can
display "the weighted-average cost after applying this receipt line"
without joining to stock_movements. Populated by services/goods_receipt.py
right after inventory.apply_purchase_in returns the new average.

Nullable because historical rows (if any) will not have it filled in.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "8058342b33b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "goods_receipt_lines",
        sa.Column("avg_cost_after", sa.Numeric(18, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("goods_receipt_lines", "avg_cost_after")
