---
description: Manually trigger demo data reset (clear transactions, re-seed historical orders)
argument-hint: [--yes-i-am-sure] [--skip-backup]
---

# /demo-reset

Manually trigger the Demo Data Reset that normally runs at 3am Malaysia time.

## Invocation

```
/demo-reset                          # confirm then run
/demo-reset --yes-i-am-sure          # skip confirmation
/demo-reset --skip-backup            # dangerous, debug only
```

## What this command does

Runs the same logic as the scheduled `demo_reset_task` Celery Beat job:

1. **Backup current state** to `/backups/before-reset-{timestamp}.sql.gz` (unless `--skip-backup`)
2. **Open transaction**
3. **Delete transactional data** (order-of-dependency):
   - audit_logs, notifications
   - credit_note_lines, credit_notes
   - invoice_lines, invoices
   - delivery_order_lines, delivery_orders
   - sales_order_lines, sales_orders
   - goods_receipt_lines, goods_receipts
   - purchase_order_lines, purchase_orders
   - stock_transfer_lines, stock_transfers
   - stock_adjustment_lines, stock_adjustments
   - stock_movements
   - payment_allocations, payments
4. **Reset stock state** to initial values:
   ```sql
   UPDATE stocks SET 
     on_hand = initial_on_hand,
     reserved = 0,
     quality_hold = 0,
     incoming = 0,
     in_transit = 0,
     avg_cost = initial_avg_cost;
   ```
5. **Re-run transactional seed** (`backend/scripts/seed_transactional.py`) to generate 6 months of historical orders
6. **Clear Redis**:
   - `FLUSHDB 1` (cache)
   - `FLUSHDB 2` (session)
   - Keep DB 3 (sequence) — but reset keys matching `seq:*:2026` to current counts
7. **Clean temp uploads**:
   - Delete files in `/uploads/ocr/*` older than 1 day
   - Delete files in `/uploads/imports/*` older than 1 day
8. **Write to `demo_reset_logs`** table
9. **Send Slack / email alert** with summary

## Preserved (NOT deleted)

- organizations, users, roles, permissions, user_roles, role_permissions
- warehouses, currencies, exchange_rates, tax_rates, uoms
- brands, categories, msic_codes
- skus, suppliers, customers
- settings (user preferences, org ai_features)
- e-invoice PDFs (for reference)

## Instructions for Claude

### Step 1: Confirmation

Unless `--yes-i-am-sure` is present, confirm with the user:
```
⚠️  About to reset DEMO data:
    - Delete all orders, invoices, stock movements, notifications
    - Reset inventory to initial state
    - Re-seed 6 months of historical transactions
    - Clear cache + sessions
    
    Backup will be created at: /backups/before-reset-{YYYYMMDDHHMMSS}.sql.gz

Proceed? [y/N]
```

### Step 2: Run via API or CLI

**Preferred (Admin API):**
```bash
curl -X POST https://demo.yourdomain.com/api/admin/demo-reset \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"skip_backup": false}'
```

**Direct Celery (via docker exec):**
```bash
docker compose exec backend python -m app.tasks.demo_reset --manual
```

**Local dev:**
```bash
cd backend && python scripts/demo_reset.py --manual
```

### Step 3: Stream logs

Tail logs and show progress:
```bash
docker compose logs -f celery-worker-default | grep demo_reset
```

Expected output:
```
[demo_reset] backup started → /backups/before-reset-20260423_150000.sql.gz
[demo_reset] backup complete (48MB)
[demo_reset] deleted 500 purchase_orders
[demo_reset] deleted 1200 sales_orders
[demo_reset] deleted 2003 stock_movements
[demo_reset] reset 600 stock records
[demo_reset] re-seeded 150 POs, 300 SOs, 250 invoices
[demo_reset] cleared redis db 1 (cache)
[demo_reset] cleared redis db 2 (session)
[demo_reset] removed 47 temp files
[demo_reset] COMPLETED in 42s
```

### Step 4: Verify

After success, run a quick sanity check:
```bash
# counts match expected
docker compose exec backend python -c "
from app.models import *
from app.core.database import async_session
# ... assert 500 transactional records
"
```

### Step 5: Report

```
✅ Demo data reset complete
   Duration: 42 seconds
   Backup: /backups/before-reset-20260423_150000.sql.gz (48MB)
   Deleted: 3,756 records
   Re-seeded: 700 transactional records
   Redis cleared: cache (db 1), session (db 2)
   
   System ready for next demo.
```

## Failure handling

If any step fails:
1. **Rollback transaction** — original data restored
2. **Alert**: log + email/Slack to admin
3. **Log**: add record to `demo_reset_logs` with `status=ROLLED_BACK` and error message
4. **Inform user** to investigate before retrying

## Safety

- This command is **destructive**. Never run on production.
- Admin role required (check current_user.role == 'admin' before executing API call)
- Cannot run if another reset is already in progress (check `demo_reset_logs.status = 'RUNNING'`)
- Recent backup (< 24h) must exist or `--skip-backup` must be provided

## Related

- Scheduled trigger: Celery Beat `crontab(hour=3, minute=0, timezone='Asia/Kuala_Lumpur')`
- Implementation: `backend/app/tasks/demo_reset.py`
- Admin UI button: `/admin/demo-reset` (only Admin role)
