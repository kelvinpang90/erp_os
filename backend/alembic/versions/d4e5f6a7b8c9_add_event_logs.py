"""add event_logs table for admin dev-tools event stream

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-06 12:00:00.000000

Window 17 introduces an Admin Dev Tools page that streams the EventBus
in real time and lets the operator scroll back through recent events.
The table is intentionally append-only and trimmed by the application
layer to the most recent ~1000 rows so it never bloats the database.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )
    op.create_index("ix_eventlog_occurred", "event_logs", ["occurred_at"])
    op.create_index(
        "ix_eventlog_org_type",
        "event_logs",
        ["organization_id", "event_type", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_eventlog_org_type", table_name="event_logs")
    op.drop_index("ix_eventlog_occurred", table_name="event_logs")
    op.drop_table("event_logs")
