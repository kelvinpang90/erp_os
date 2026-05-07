// Shared types for the Dashboard page — mirror backend schemas/dashboard.py.
// Decimal fields arrive as strings (Pydantic JSON encoder); we parse to
// number only at the chart layer to avoid float drift in totals.

export interface DashboardKPIs {
  today_sales: string
  today_purchases: string
  pending_shipments: number
  low_stock_count: number
  pending_einvoices: number
  ai_cost_today_usd: string
}

export interface AISummaryContent {
  headline: string
  key_findings: string[]
  action_items: string[]
}

export interface AISummaryPayload {
  en: AISummaryContent
  zh: AISummaryContent
}

export interface AISummaryEnvelope {
  available: boolean
  payload: AISummaryPayload | null
  is_stale: boolean
  staleness_seconds: number
  generated_at: string | null
  error_code: string | null
}

export interface TrendPoint {
  bucket: string
  value: string
}

export interface StatusBucket {
  status: string
  count: number
}

export interface DashboardTrends {
  sales_last_30d: TrendPoint[]
  purchase_last_30d: TrendPoint[]
  einvoice_status_distribution: StatusBucket[]
  ai_cost_last_30d: TrendPoint[]
}

export interface DashboardOverviewResponse {
  kpis: DashboardKPIs
  summary: AISummaryEnvelope
  trends: DashboardTrends
  cache_hit: boolean
  refreshed_at: string
}
