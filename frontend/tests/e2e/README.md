# E2E tests (Playwright)

Three golden-path specs lock the demo flow:

- `purchase.spec.ts` — OCR mock → PO confirm → goods receipt → FULLY_RECEIVED
- `sales.spec.ts` — SO confirm → DO ship → invoice precheck → submit → VALIDATED
- `inventory.spec.ts` — branch matrix render → KL→Penang transfer → ship → receive

UI is driven only for login + status-badge assertions; business writes go
through the API to avoid ProForm/EditableProTable widget brittleness.
OCR is mocked via `page.route()` (zero cost, deterministic). MyInvois runs
in mock mode (`MYINVOIS_MODE=mock`) so submit returns a fake UIN.

## Local run (against docker compose)

```bash
docker compose up -d --wait
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed_master_data.py
docker compose exec backend python scripts/seed_all_master.py

cd frontend
npx playwright install --with-deps chromium
E2E_BASE_URL=http://localhost npx playwright test
npx playwright show-report
```

Single spec / debug:

```bash
npx playwright test purchase.spec.ts --headed --debug
```

## CI

`.github/workflows/nightly-e2e.yml` runs the full set every night at 18:00 UTC.
Failures upload `playwright-report/` (HTML + traces + videos) as artifacts.
