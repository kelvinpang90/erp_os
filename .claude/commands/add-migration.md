---
description: Create a new Alembic migration file with proper boilerplate and latest down_revision
argument-hint: <short_description_snake_case>
---

# /add-migration

Generate a new Alembic migration skeleton for erp-os backend.

## Invocation

```
/add-migration add_safety_stock_to_skus
/add-migration create_consolidated_invoice_flag
/add-migration index_invoice_validated_at
```

## What this command does

1. **Reads latest migration** from `backend/alembic/versions/` to find current HEAD
2. **Generates new migration file** `{timestamp}_{description}.py`
3. **Fills in boilerplate**:
   - Unique `revision` ID (12-char hex)
   - `down_revision` = latest migration
   - Empty `upgrade()` and `downgrade()` functions with TODO comments
4. **Asks user what to migrate** if not obvious, then fills in the SQL / ORM DDL

## Instructions for Claude

### Step 1: Parse the description
- `$ARGUMENTS` should be snake_case, describing the change
- Reject if empty or has spaces/dashes

### Step 2: Find latest migration
```bash
cd backend && ls -t alembic/versions/*.py | head -1
# Read its `revision = "..."` line → use as down_revision
```

### Step 3: Generate filename and revision ID
```python
import secrets
from datetime import datetime

timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
revision_id = secrets.token_hex(6)  # 12 chars
filename = f"{timestamp}_{revision_id}_{description}.py"
```

### Step 4: Write the migration file

Template:
```python
"""${short_description_human_readable}

Revision ID: ${revision_id}
Revises: ${down_revision}
Create Date: ${create_date_iso}

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "${revision_id}"
down_revision: str | None = "${down_revision}"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Apply migration."""
    # TODO: implement schema change
    # Examples:
    #   op.add_column("skus", sa.Column("safety_stock", sa.Numeric(18, 4), nullable=False, server_default="0"))
    #   op.create_index("ix_invoices_validated_at", "invoices", ["status", "validated_at"])
    #   op.drop_constraint("fk_old", "skus", type_="foreignkey")
    raise NotImplementedError("TODO: implement upgrade()")


def downgrade() -> None:
    """Revert migration."""
    # TODO: mirror the upgrade() in reverse order
    raise NotImplementedError("TODO: implement downgrade()")
```

### Step 5: Ask user for the actual change
```
Created skeleton at: backend/alembic/versions/{filename}

What schema change do you want to make? Describe in plain English, e.g.:
  "Add a safety_stock column (Numeric 18,4) to skus"
  "Create an index on (status, validated_at) for invoices"
  "Drop the old fk_suppliers_currency constraint"

I'll fill in upgrade() and downgrade() for you.
```

### Step 6: Fill in upgrade/downgrade

Based on user's description, generate Alembic `op.*` calls:
- `op.add_column(...)` / `op.drop_column(...)`
- `op.create_index(...)` / `op.drop_index(...)`
- `op.create_table(...)` / `op.drop_table(...)`
- `op.alter_column(...)`
- `op.create_foreign_key(...)` / `op.drop_constraint(...)`
- For data migration: `op.execute(sa.text("..."))` or `op.bulk_insert(...)`

### Step 7: Remind user to test
```
✅ Migration created: {filename}

Before merging:
  cd backend
  alembic upgrade head         # apply
  alembic downgrade -1         # verify rollback works
  alembic upgrade head         # re-apply
  pytest tests/                # tests still pass?
```

## Rules

- **Never** use `create_all()` — all schema changes must go through Alembic
- Migrations must be **reversible** (downgrade must work)
- For MySQL: **avoid renames** (prefer add new + backfill + drop old)
- Data migrations and schema migrations should be **separate** when possible
- Index creation on large tables should note `algorithm=INPLACE` if applicable

## Related

- `CLAUDE.md` E7: no `create_all()`, only Alembic
- `docs/ddl.sql`: initial schema reference
