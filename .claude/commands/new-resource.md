---
description: Generate full CRUD stack for a new resource (backend + frontend + migration + tests)
argument-hint: <ResourceName> [with <field_list>]
---

# /new-resource

Scaffold a complete CRUD resource module for erp-os following CLAUDE.md conventions.

## Invocation

```
/new-resource Warehouse
/new-resource Brand with code/name/logo_url
/new-resource TaxRate like Supplier
```

## What this command does

Executes the `new-resource` skill to generate the standard 5-layer stack + frontend + tests.

**Backend files (9):**
1. `backend/app/models/$ARG_SNAKE.py` — SQLAlchemy ORM model
2. `backend/app/schemas/$ARG_SNAKE.py` — Pydantic Create/Update/Response/Detail schemas
3. `backend/app/repositories/$ARG_SNAKE.py` — Data access layer
4. `backend/app/services/$ARG_SNAKE.py` — Business logic
5. `backend/app/routers/$ARG_SNAKE.py` — FastAPI endpoints
6. `backend/tests/unit/test_$ARG_SNAKE_service.py` — Service unit tests
7. `backend/tests/integration/test_$ARG_SNAKE_router.py` — API integration tests
8. `backend/tests/factories/$ARG_SNAKE.py` — factory-boy test data factory
9. `backend/alembic/versions/$TS_add_$ARG_SNAKE.py` — Alembic migration

**Frontend files (3):**
10. `frontend/src/pages/$ARG_PASCAL/ListPage.tsx`
11. `frontend/src/pages/$ARG_PASCAL/EditPage.tsx`
12. `frontend/src/pages/$ARG_PASCAL/columns.tsx`

**Config updates:**
- Register router in `backend/app/main.py`
- Add route in `frontend/src/App.tsx`
- Add permissions to `backend/scripts/seed_master_data.py`
- Append i18n keys to `frontend/src/locales/{en-US,zh-CN}/$ARG_SNAKE.json`

## Parameters

- **$ARGUMENTS**: Resource name in PascalCase (e.g., `Warehouse`)

## Expected input format

The command will:
1. Parse the resource name from arguments
2. Derive snake_case / kebab-case / plural forms automatically
3. Ask for field definitions if not provided (or inferred from "like X" clause)

## Instructions for Claude

1. **Load the `new-resource` skill** — read `.claude/skills/new-resource/SKILL.md` for detailed generation logic
2. **Derive naming variants:**
   - `$ARG_PASCAL` = "Warehouse"
   - `$ARG_SNAKE` = "warehouse"
   - `$ARG_SNAKE_PLURAL` = "warehouses"
   - `$ARG_KEBAB` = "warehouse"
3. **Ask for field definitions** if not given:
   ```
   Please provide fields for $ARG_PASCAL as `name: type [, constraints]`.
   Example:
     code: str (unique, max 32)
     name: str (max 120)
     type: Enum(MAIN, BRANCH, TRANSIT)
     address: str (optional, max 200)
   ```
4. **Generate all files using skill templates** in `.claude/skills/new-resource/templates/`
5. **Verify checklist** before reporting done:
   - [ ] All files created, no overwrites
   - [ ] Migration `down_revision` points to latest
   - [ ] Model inherits correct mixins
   - [ ] Service enforces `organization_id` isolation
   - [ ] Router has `Depends(get_current_user)`
   - [ ] Tests cover: success, duplicate, not_found, permission_denied, soft_delete
   - [ ] i18n keys in both en-US and zh-CN
6. **Output summary** with next steps:
   ```
   ✅ Generated 13 files for Warehouse resource
   
   Next steps:
     1. Review files
     2. cd backend && alembic upgrade head
     3. cd frontend && npm run gen:api
     4. pytest backend/tests/unit/test_warehouse_service.py -v
     5. Add menu item (UI-side is seeded by backend)
   ```

## Do NOT

- Generate business-flow specific logic (like status transitions for PO/SO) — use `/new-resource` only for standard CRUD
- Skip tests
- Hardcode organization_id (always read from `current_user`)
- Use `HTTPException` directly (use custom `AppException` subclasses)
