/**
 * E2E-1: Purchase loop
 *   Login (purchaser) → OCR upload (mocked) → PO create+confirm
 *   → Goods receipt → stock 6-axis updated → PO FULLY_RECEIVED
 *
 * UI is driven for: login, OCR navigation chain, status badge assertions.
 * Business writes go through the API to avoid ProForm/EditableProTable
 * widget-internal selectors that are brittle to translation/layout tweaks.
 */

import { expect, test } from '@playwright/test'
import { loginViaUI } from './fixtures/auth'
import { loginAsRole, getStock, todayISO, type ApiClient } from './fixtures/api'
import { pickInventoryBaseline, pickFirstSupplier } from './fixtures/test-data'

test.describe.serial('E2E-1 Purchase loop', () => {
  let api: ApiClient
  let baseline: Awaited<ReturnType<typeof pickInventoryBaseline>>
  let supplierId: number

  test.beforeAll(async ({ baseURL }) => {
    api = await loginAsRole(baseURL!, 'purchaser')
    baseline = await pickInventoryBaseline(api)
    const sup = await pickFirstSupplier(api)
    supplierId = sup.id
  })

  test.afterAll(async () => {
    await api?.dispose()
  })

  test('OCR upload mock streams SSE → navigates to PO create', async ({ page }) => {
    await loginViaUI(page, 'purchaser')

    const ocrResult = {
      supplier_name: 'Acme Supplies Sdn Bhd',
      supplier_tin: 'C12345678901',
      supplier_address: 'Lot 1, Kuala Lumpur',
      invoice_no: 'INV-MOCK-001',
      business_date: todayISO(),
      currency: 'MYR',
      subtotal_excl_tax: '100.00',
      tax_amount: '0.00',
      total_incl_tax: '100.00',
      lines: [
        {
          description: baseline.sku.name ?? 'Test item',
          sku_code: baseline.sku.code ?? '',
          qty: '1',
          uom: null,
          unit_price_excl_tax: '100.00',
          tax_rate_percent: '0',
          discount_percent: '0',
        },
      ],
      remarks: 'mocked by E2E',
      confidence: 'high' as const,
    }

    await page.route('**/api/ai/ocr/purchase-order', async (route) => {
      const body = [
        `event: progress\ndata: ${JSON.stringify({ stage: 'uploaded', progress: 20 })}\n\n`,
        `event: progress\ndata: ${JSON.stringify({ stage: 'calling_ai', progress: 50 })}\n\n`,
        `event: progress\ndata: ${JSON.stringify({ stage: 'parsing', progress: 80 })}\n\n`,
        `event: done\ndata: ${JSON.stringify({ stage: 'done', progress: 100, result: ocrResult })}\n\n`,
      ].join('')
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
        body,
      })
    })

    await page.goto('/purchase/orders/ocr-upload')

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'mock-invoice.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 mock\n'),
    })

    // SSE done event triggers a 400ms-delayed nav to /purchase/orders/create
    await page.waitForURL('**/purchase/orders/create', { timeout: 15_000 })
  })

  test('PO API loop: create → confirm → goods receipt → FULLY_RECEIVED', async ({ page }) => {
    const before = await getStock(api, baseline.sku.id, baseline.warehouseKL.id)

    // 1. Create PO
    const created = await api.post<{ id: number; document_no: string; status: string }>(
      '/purchase-orders',
      {
        supplier_id: supplierId,
        warehouse_id: baseline.warehouseKL.id,
        business_date: todayISO(),
        currency: 'MYR',
        exchange_rate: 1,
        payment_terms_days: 30,
        lines: [
          {
            sku_id: baseline.sku.id,
            uom_id: baseline.sku.base_uom_id,
            qty_ordered: 3,
            unit_price_excl_tax: 50,
            tax_rate_id: baseline.sku.tax_rate_id ?? baseline.taxRateId,
          },
        ],
      },
    )
    expect(created.status).toBe('DRAFT')

    // 2. Confirm PO → incoming should rise
    await api.post(`/purchase-orders/${created.id}/confirm`)
    const afterConfirm = await getStock(api, baseline.sku.id, baseline.warehouseKL.id)
    expect(Number(afterConfirm.incoming) - Number(before.incoming)).toBeCloseTo(3, 4)

    // 3. UI: detail page shows CONFIRMED
    await loginViaUI(page, 'purchaser')
    await page.goto(`/purchase/orders/${created.id}`)
    await expect(page.locator('[data-testid="po-status"]')).toContainText('CONFIRMED', {
      timeout: 10_000,
    })

    // 4. Receive full quantity via API
    const detail = await api.get<{ lines: { id: number; qty_ordered: string }[] }>(
      `/purchase-orders/${created.id}`,
    )
    await api.post('/goods-receipts', {
      purchase_order_id: created.id,
      receipt_date: todayISO(),
      lines: detail.lines.map((l) => ({
        purchase_order_line_id: l.id,
        qty_received: Number(l.qty_ordered),
      })),
    })

    // 5. Stock: on_hand +3, incoming back to baseline
    const afterGR = await getStock(api, baseline.sku.id, baseline.warehouseKL.id)
    expect(Number(afterGR.on_hand) - Number(before.on_hand)).toBeCloseTo(3, 4)
    expect(Number(afterGR.incoming) - Number(before.incoming)).toBeCloseTo(0, 4)

    // 6. UI: detail page now shows FULLY_RECEIVED
    await page.reload()
    await expect(page.locator('[data-testid="po-status"]')).toContainText('FULLY RECEIVED', {
      timeout: 10_000,
    })
  })
})
