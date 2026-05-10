/**
 * E2E-2: Sales loop
 *   Login (sales) → SO create+confirm → DO ship → Invoice generate
 *   → Precheck → Submit → VALIDATED + UIN
 *
 * MyInvois adapter is in mock mode by default (settings.MYINVOIS_MODE=mock),
 * so submit returns a fake UIN without external calls.
 */

import { expect, test } from '@playwright/test'
import { loginViaUI } from './fixtures/auth'
import { loginAsRole, getStock, todayISO, type ApiClient } from './fixtures/api'
import { pickInventoryBaseline, pickB2BCustomer } from './fixtures/test-data'

test.describe.serial('E2E-2 Sales loop', () => {
  let api: ApiClient
  let baseline: Awaited<ReturnType<typeof pickInventoryBaseline>>
  let customerId: number
  // Shared across tests in this describe — annotations don't survive between tests.
  let soId = 0
  let invoiceId = 0

  test.beforeAll(async ({ baseURL }) => {
    api = await loginAsRole(baseURL!, 'sales')
    baseline = await pickInventoryBaseline(api)
    const cust = await pickB2BCustomer(api)
    customerId = cust.id
  })

  test.afterAll(async () => {
    await api?.dispose()
  })

  test('SO create → confirm reserves stock', async () => {
    const before = await getStock(api, baseline.sku.id, baseline.warehouseKL.id)

    const created = await api.post<{ id: number; status: string }>('/sales-orders', {
      customer_id: customerId,
      warehouse_id: baseline.warehouseKL.id,
      business_date: todayISO(),
      currency: 'MYR',
      exchange_rate: 1,
      payment_terms_days: 30,
      lines: [
        {
          sku_id: baseline.sku.id,
          uom_id: baseline.sku.base_uom_id,
          qty_ordered: 2,
          unit_price_excl_tax: Number(baseline.sku.unit_price_excl_tax) || 100,
          tax_rate_id: baseline.sku.tax_rate_id ?? baseline.taxRateId,
        },
      ],
    })
    expect(created.status).toBe('DRAFT')
    soId = created.id

    await api.post(`/sales-orders/${soId}/confirm`)
    const after = await getStock(api, baseline.sku.id, baseline.warehouseKL.id)
    expect(Number(after.reserved) - Number(before.reserved)).toBeCloseTo(2, 4)
    expect(Number(before.available) - Number(after.available)).toBeCloseTo(2, 4)
  })

  test('DO ship full → on_hand drops, reserved cleared, SO FULLY_SHIPPED', async ({ page }) => {
    expect(soId).toBeGreaterThan(0)
    const so = await api.get<{ lines: { id: number; qty_ordered: string }[] }>(
      `/sales-orders/${soId}`,
    )
    const before = await getStock(api, baseline.sku.id, baseline.warehouseKL.id)

    await api.post('/delivery-orders', {
      sales_order_id: soId,
      delivery_date: todayISO(),
      lines: so.lines.map((l) => ({
        sales_order_line_id: l.id,
        qty_shipped: Number(l.qty_ordered),
      })),
    })

    const after = await getStock(api, baseline.sku.id, baseline.warehouseKL.id)
    expect(Number(before.on_hand) - Number(after.on_hand)).toBeCloseTo(2, 4)
    expect(Number(before.reserved) - Number(after.reserved)).toBeCloseTo(2, 4)

    await loginViaUI(page, 'sales')
    await page.goto(`/sales/orders/${soId}`)
    await expect(page.locator('[data-testid="so-status"]')).toContainText('FULLY SHIPPED', {
      timeout: 15_000,
    })
  })

  test('Invoice generate → precheck → submit reaches VALIDATED', async ({ page }) => {
    expect(soId).toBeGreaterThan(0)

    const inv = await api.post<{ id: number; status: string }>(
      `/invoices/generate-from-so/${soId}`,
      {},
    )
    expect(inv.status).toBe('DRAFT')
    invoiceId = inv.id

    await api.post<{ status: string }>(`/invoices/${invoiceId}/precheck`, {})

    const submitted = await api.post<{ id: number; status: string; uin?: string }>(
      `/invoices/${invoiceId}/submit`,
      {},
    )
    expect(['VALIDATED', 'FINAL']).toContain(submitted.status)
    expect(submitted.uin).toBeTruthy()

    await loginViaUI(page, 'sales')
    await page.goto(`/sales/einvoice/${invoiceId}`)
    await expect(page.locator('[data-testid="invoice-status"]')).toBeVisible({
      timeout: 15_000,
    })
    await expect(page.locator('[data-testid="invoice-status"]')).not.toContainText('DRAFT')
  })
})
