/**
 * Selects baseline test data via API at runtime so specs don't depend on
 * fixed seed IDs. Each spec calls `pickPurchaseBaseline` / etc. once in
 * beforeAll and reuses the resolved IDs.
 */

import { listRefs, getStock, type ApiClient, type SkuRef, type RefItem } from './api'

interface Baseline {
  warehouseKL: RefItem
  warehousePenang: RefItem
  sku: SkuRef
  taxRateId: number
}

async function pickWarehouses(api: ApiClient): Promise<{ kl: RefItem; penang: RefItem }> {
  const items = await listRefs(api, '/warehouses')
  const active = items.filter((w) => w.is_active !== false)
  if (active.length < 2) {
    throw new Error(`Expected ≥2 active warehouses, got ${active.length}`)
  }
  // Prefer name-matching to keep KL→Penang direction stable for inventory tests
  const kl =
    active.find((w) => /kuala\s*lumpur|kl|main/i.test(w.name ?? '')) ?? active[0]
  const penang =
    active.find((w) => /penang|pulau/i.test(w.name ?? '') && w.id !== kl.id) ??
    active.find((w) => w.id !== kl.id)!
  return { kl, penang }
}

async function pickStockedSku(
  api: ApiClient,
  warehouseId: number,
  minOnHand: number,
): Promise<SkuRef> {
  // Pull the first 100 SKUs and probe stocks in order. Seed gives ~200 SKUs
  // each with initial stock so a hit usually comes within the first few.
  const res = await api.get<{ items: SkuRef[] }>('/skus?page_size=100')
  const skus = res.items.filter((s) => s.is_active !== false)
  for (const sku of skus) {
    try {
      const stock = await getStock(api, sku.id, warehouseId)
      // available = on_hand - reserved - quality_hold; need positive available too
      if (Number(stock.on_hand) >= minOnHand && Number(stock.available) >= minOnHand) {
        return sku
      }
    } catch {
      /* continue */
    }
  }
  throw new Error(`No SKU with on_hand ≥${minOnHand} found in warehouse ${warehouseId}`)
}

async function pickAnyTaxRate(api: ApiClient): Promise<number> {
  const res = await api.get<{ items: { id: number; rate: string }[] }>('/tax-rates?page_size=20')
  // Prefer 0% to avoid SST math edge cases in this test scaffolding.
  const zero = res.items.find((t) => Number(t.rate) === 0)
  return (zero ?? res.items[0]).id
}

export async function pickInventoryBaseline(api: ApiClient): Promise<Baseline> {
  const { kl, penang } = await pickWarehouses(api)
  const sku = await pickStockedSku(api, kl.id, 10)
  const taxRateId = await pickAnyTaxRate(api)
  return { warehouseKL: kl, warehousePenang: penang, sku, taxRateId }
}

export async function pickFirstSupplier(api: ApiClient): Promise<RefItem> {
  const items = await listRefs(api, '/suppliers')
  const active = items.filter((s) => s.is_active !== false)
  if (active.length === 0) throw new Error('No active suppliers in seed data')
  return active[0]
}

export async function pickB2BCustomer(api: ApiClient): Promise<RefItem & { tin?: string }> {
  // List customers; prefer those with a TIN and customer_type B2B for invoice flow.
  const res = await api.get<{
    items: (RefItem & { tin?: string; customer_type?: string })[]
  }>('/customers?page_size=100')
  const active = res.items.filter((c) => c.is_active !== false)
  const b2b = active.find((c) => c.customer_type === 'B2B' && c.tin)
  if (b2b) return b2b
  if (active.length === 0) throw new Error('No active customers in seed data')
  return active[0]
}
