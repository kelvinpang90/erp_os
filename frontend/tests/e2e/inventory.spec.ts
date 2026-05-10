/**
 * E2E-3: Inventory loop
 *   Login (manager) → Branch matrix → StockTransfer create → confirm
 *   → ship-out → receive → Penang on_hand up, KL on_hand back, RECEIVED status.
 *
 * Manager role has full read/write across both warehouses, so a single
 * api context handles both ends of the transfer.
 */

import { expect, test } from '@playwright/test'
import { loginViaUI } from './fixtures/auth'
import { loginAsRole, getStock, todayISO, type ApiClient } from './fixtures/api'
import { pickInventoryBaseline } from './fixtures/test-data'

test.describe.serial('E2E-3 Inventory loop', () => {
  let api: ApiClient
  let baseline: Awaited<ReturnType<typeof pickInventoryBaseline>>

  test.beforeAll(async ({ baseURL }) => {
    api = await loginAsRole(baseURL!, 'manager')
    baseline = await pickInventoryBaseline(api)
  })

  test.afterAll(async () => {
    await api?.dispose()
  })

  test('Branch inventory matrix page loads without error', async ({ page }) => {
    await loginViaUI(page, 'manager')

    // Wait for the data fetch instead of a specific DOM node — matrix
    // renders either an Ant Table OR an Empty component depending on data.
    const matrixResp = page.waitForResponse(
      (r) => r.url().includes('/api/inventory/branch-matrix') && r.status() === 200,
      { timeout: 20_000 },
    )
    await page.goto('/inventory/branch-matrix')
    await matrixResp

    // After response, either rows render OR the empty state shows. Both
    // mean the page didn't crash. Loading spinner should be gone.
    await expect(page.locator('.ant-spin-spinning')).toHaveCount(0, { timeout: 10_000 })
  })

  test('Stock transfer KL → Penang: confirm → ship → receive', async ({ page }) => {
    const klBefore = await getStock(api, baseline.sku.id, baseline.warehouseKL.id)
    const penBefore = await getStock(api, baseline.sku.id, baseline.warehousePenang.id)

    // 1. Create transfer
    const created = await api.post<{ id: number; status: string; lines: { id: number }[] }>(
      '/stock-transfers',
      {
        from_warehouse_id: baseline.warehouseKL.id,
        to_warehouse_id: baseline.warehousePenang.id,
        business_date: todayISO(),
        lines: [
          {
            sku_id: baseline.sku.id,
            uom_id: baseline.sku.base_uom_id,
            qty_sent: 3,
          },
        ],
      },
    )
    expect(created.status).toBe('DRAFT')

    // 2. Confirm: KL.reserved += 3
    const confirmed = await api.post<{ status: string; lines: { id: number }[] }>(
      `/stock-transfers/${created.id}/confirm`,
    )
    expect(confirmed.status).toBe('CONFIRMED')
    const afterConfirm = await getStock(api, baseline.sku.id, baseline.warehouseKL.id)
    expect(Number(afterConfirm.reserved) - Number(klBefore.reserved)).toBeCloseTo(3, 4)

    // 3. Ship-out: KL.on_hand -= 3, KL.reserved -= 3, KL.in_transit (or destination's incoming) reflects movement
    const shipped = await api.post<{ status: string }>(`/stock-transfers/${created.id}/ship-out`)
    expect(shipped.status).toBe('IN_TRANSIT')
    const afterShip = await getStock(api, baseline.sku.id, baseline.warehouseKL.id)
    expect(Number(klBefore.on_hand) - Number(afterShip.on_hand)).toBeCloseTo(3, 4)

    // 4. Receive at Penang: full quantity
    const lineIds = confirmed.lines.map((l) => l.id)
    const received = await api.post<{ status: string }>(
      `/stock-transfers/${created.id}/receive`,
      {
        lines: lineIds.map((line_id) => ({ line_id, qty_received: 3 })),
      },
    )
    expect(received.status).toBe('RECEIVED')

    // 5. Stocks: Penang.on_hand += 3
    const penAfter = await getStock(api, baseline.sku.id, baseline.warehousePenang.id)
    expect(Number(penAfter.on_hand) - Number(penBefore.on_hand)).toBeCloseTo(3, 4)

    // 6. UI: detail page shows RECEIVED
    await loginViaUI(page, 'manager')
    await page.goto(`/inventory/transfers/${created.id}`)
    await expect(page.locator('[data-testid="transfer-status"]')).toContainText(/RECEIVED/i, {
      timeout: 10_000,
    })
  })
})
