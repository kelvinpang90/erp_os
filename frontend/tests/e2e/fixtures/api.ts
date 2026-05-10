/**
 * Backend API helpers for E2E tests.
 *
 * Why not always go through the UI? ProForm + EditableProTable have heavy
 * widget internals that make UI-driven business setup brittle. Tests use
 * the UI for the user-facing critical paths (login, navigation, status
 * badges) and call the API directly for bulk state setup and assertions.
 */

import type { APIRequestContext, APIResponse } from '@playwright/test'
import { request as pwRequest } from '@playwright/test'

export type DemoRole = 'admin' | 'manager' | 'sales' | 'purchaser'

export const DEMO_CREDENTIALS: Record<DemoRole, { email: string; password: string }> = {
  admin: { email: 'admin@demo.my', password: 'Admin@123' },
  manager: { email: 'manager@demo.my', password: 'Manager@123' },
  sales: { email: 'sales@demo.my', password: 'Sales@123' },
  purchaser: { email: 'purchaser@demo.my', password: 'Purchaser@123' },
}

export interface ApiClient {
  ctx: APIRequestContext
  token: string
  get: <T = unknown>(path: string) => Promise<T>
  post: <T = unknown>(path: string, body?: unknown) => Promise<T>
  patch: <T = unknown>(path: string, body?: unknown) => Promise<T>
  raw: (method: string, path: string, body?: unknown) => Promise<APIResponse>
  dispose: () => Promise<void>
}

async function readJsonOrThrow<T>(res: APIResponse, method: string, path: string): Promise<T> {
  if (!res.ok()) {
    let body = ''
    try {
      body = await res.text()
    } catch {
      /* ignore */
    }
    throw new Error(`${method} ${path} → ${res.status()} ${res.statusText()}: ${body.slice(0, 500)}`)
  }
  if (res.status() === 204) return undefined as T
  return (await res.json()) as T
}

export async function loginAsRole(
  baseURL: string,
  role: DemoRole,
): Promise<ApiClient> {
  const ctx = await pwRequest.newContext({ baseURL })
  const creds = DEMO_CREDENTIALS[role]
  const loginRes = await ctx.post('/api/auth/login', { data: creds })
  const loginBody = await readJsonOrThrow<{ access_token: string }>(
    loginRes,
    'POST',
    '/api/auth/login',
  )
  const token = loginBody.access_token

  const headers = { Authorization: `Bearer ${token}` }

  return {
    ctx,
    token,
    async get<T>(path: string): Promise<T> {
      const res = await ctx.get(`/api${path}`, { headers })
      return readJsonOrThrow<T>(res, 'GET', `/api${path}`)
    },
    async post<T>(path: string, body?: unknown): Promise<T> {
      const res = await ctx.post(`/api${path}`, { headers, data: body ?? {} })
      return readJsonOrThrow<T>(res, 'POST', `/api${path}`)
    },
    async patch<T>(path: string, body?: unknown): Promise<T> {
      const res = await ctx.patch(`/api${path}`, { headers, data: body ?? {} })
      return readJsonOrThrow<T>(res, 'PATCH', `/api${path}`)
    },
    async raw(method: string, path: string, body?: unknown): Promise<APIResponse> {
      return ctx.fetch(`/api${path}`, {
        method,
        headers,
        data: body !== undefined ? body : undefined,
      })
    },
    async dispose() {
      await ctx.dispose()
    },
  }
}

// ── Domain types — minimal subsets used by the specs ──────────────────────

export interface RefItem {
  id: number
  code?: string
  name?: string
  is_active?: boolean
}

export interface SkuRef extends RefItem {
  base_uom_id: number
  unit_price_excl_tax: string
  tax_rate_id: number
  tax_rate?: { rate: string }
}

export interface StockSnapshot {
  sku_id: number
  warehouse_id: number
  on_hand: string
  reserved: string
  quality_hold: string
  available: string
  incoming: string
  in_transit: string
  avg_cost: string
}

export async function listRefs(api: ApiClient, path: string, pageSize = 100): Promise<RefItem[]> {
  const res = await api.get<{ items: RefItem[] }>(`${path}?page_size=${pageSize}`)
  return res.items ?? []
}

export async function getStock(
  api: ApiClient,
  skuId: number,
  warehouseId: number,
): Promise<StockSnapshot> {
  return api.get<StockSnapshot>(
    `/inventory/stocks?sku_id=${skuId}&warehouse_id=${warehouseId}`,
  )
}

export function decimalDelta(after: string, before: string): number {
  return Number(after) - Number(before)
}

/** Today's date as YYYY-MM-DD (UTC; the ERP stores business_date independent of TZ). */
export function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}
