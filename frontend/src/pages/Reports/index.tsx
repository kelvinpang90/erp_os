import { Card, Col, Empty, Radio, Row, Space, Spin, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { axiosInstance } from '../../api/client'

const COLORS = ['#1677ff', '#13c2c2', '#fa8c16', '#722ed1', '#cf1322', '#52c41a', '#eb2f96', '#a0d911']

interface TrendPoint {
  bucket: string
  value: string
}
interface TrendSeriesResponse {
  points: TrendPoint[]
  total: string
  days: number
}
interface TopEntityRow {
  id: number
  code: string
  name: string
  name_zh?: string | null
  qty: string
  amount: string
}
interface TopEntityResponse {
  rows: TopEntityRow[]
  days: number
}
interface CategoryRow {
  category_id: number | null
  category_name: string
  amount: string
  share_pct: string
}
interface CategoryShareResponse {
  rows: CategoryRow[]
  total: string
  days: number
}
interface InvTurnoverRow {
  sku_id: number
  sku_code: string
  sku_name: string
  cogs: string
  avg_inventory_value: string
  turnover_ratio: string
}
interface InvTurnoverResponse {
  rows: InvTurnoverRow[]
  days: number
}
interface WarehouseRow {
  warehouse_id: number
  warehouse_code: string
  warehouse_name: string
  on_hand_value: string
  sku_count: number
}
interface WarehouseDistResponse {
  rows: WarehouseRow[]
  total_value: string
}
interface StatusBucket {
  status: string
  count: number
}
interface EInvoiceDistResponse {
  rows: StatusBucket[]
  total: number
}
interface FeatureCostRow {
  feature: string
  calls: number
  cost_usd: string
}
interface AICostResponse {
  series: TrendPoint[]
  total_cost_usd: string
  total_calls: number
  by_feature: FeatureCostRow[]
  days: number
}

interface Bundle {
  sales: TrendSeriesResponse | null
  purchase: TrendSeriesResponse | null
  topSkus: TopEntityResponse | null
  topSuppliers: TopEntityResponse | null
  topCustomers: TopEntityResponse | null
  turnover: InvTurnoverResponse | null
  warehouse: WarehouseDistResponse | null
  category: CategoryShareResponse | null
  einvoice: EInvoiceDistResponse | null
  aiCost: AICostResponse | null
}

const EMPTY_BUNDLE: Bundle = {
  sales: null,
  purchase: null,
  topSkus: null,
  topSuppliers: null,
  topCustomers: null,
  turnover: null,
  warehouse: null,
  category: null,
  einvoice: null,
  aiCost: null,
}

function lineData(points: TrendPoint[]) {
  return points.map((p) => ({ date: p.bucket.slice(5), value: Number.parseFloat(p.value) }))
}

export default function ReportsPage() {
  const { t } = useTranslation('reports')
  const [days, setDays] = useState(30)
  const [bundle, setBundle] = useState<Bundle>(EMPTY_BUNDLE)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    setLoading(true)
    Promise.all([
      axiosInstance.get<TrendSeriesResponse>(`/reports/sales-trend?days=${days}`),
      axiosInstance.get<TrendSeriesResponse>(`/reports/purchase-trend?days=${days}`),
      axiosInstance.get<TopEntityResponse>(`/reports/top-skus?days=${days}`),
      axiosInstance.get<TopEntityResponse>(`/reports/top-suppliers?days=${days}`),
      axiosInstance.get<TopEntityResponse>(`/reports/top-customers?days=${days}`),
      axiosInstance.get<InvTurnoverResponse>(`/reports/inventory-turnover?days=${days}`),
      axiosInstance.get<WarehouseDistResponse>(`/reports/warehouse-stock-distribution`),
      axiosInstance.get<CategoryShareResponse>(`/reports/category-sales-share?days=${days}`),
      axiosInstance.get<EInvoiceDistResponse>(`/reports/einvoice-status-distribution?days=${days}`),
      axiosInstance.get<AICostResponse>(`/reports/ai-cost?days=${days}`),
    ])
      .then(([sales, purchase, topSkus, topSuppliers, topCustomers, turnover, warehouse, category, einvoice, aiCost]) => {
        if (!alive) return
        setBundle({
          sales: sales.data,
          purchase: purchase.data,
          topSkus: topSkus.data,
          topSuppliers: topSuppliers.data,
          topCustomers: topCustomers.data,
          turnover: turnover.data,
          warehouse: warehouse.data,
          category: category.data,
          einvoice: einvoice.data,
          aiCost: aiCost.data,
        })
      })
      .catch((err) => console.error('Reports fetch failed', err))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [days])

  const skuColumns = useMemo<ColumnsType<TopEntityRow>>(
    () => [
      { title: 'Code', dataIndex: 'code', key: 'code' },
      { title: 'Name', dataIndex: 'name', key: 'name' },
      { title: t('labels.qty'), dataIndex: 'qty', key: 'qty', align: 'right' },
      { title: t('labels.amount_short'), dataIndex: 'amount', key: 'amount', align: 'right' },
    ],
    [t],
  )
  const supplierColumns = useMemo<ColumnsType<TopEntityRow>>(
    () => [
      { title: 'Code', dataIndex: 'code', key: 'code' },
      { title: 'Name', dataIndex: 'name', key: 'name' },
      { title: t('labels.po_count'), dataIndex: 'qty', key: 'qty', align: 'right' },
      { title: t('labels.amount_short'), dataIndex: 'amount', key: 'amount', align: 'right' },
    ],
    [t],
  )
  const customerColumns = useMemo<ColumnsType<TopEntityRow>>(
    () => [
      { title: 'Code', dataIndex: 'code', key: 'code' },
      { title: 'Name', dataIndex: 'name', key: 'name' },
      { title: t('labels.so_count'), dataIndex: 'qty', key: 'qty', align: 'right' },
      { title: t('labels.amount_short'), dataIndex: 'amount', key: 'amount', align: 'right' },
    ],
    [t],
  )
  const turnoverColumns = useMemo<ColumnsType<InvTurnoverRow>>(
    () => [
      { title: 'SKU', dataIndex: 'sku_code', key: 'sku_code' },
      { title: 'Name', dataIndex: 'sku_name', key: 'sku_name' },
      { title: t('labels.cogs'), dataIndex: 'cogs', key: 'cogs', align: 'right' },
      { title: t('labels.inventory_value'), dataIndex: 'avg_inventory_value', key: 'inv', align: 'right' },
      { title: t('labels.turnover'), dataIndex: 'turnover_ratio', key: 'ratio', align: 'right' },
    ],
    [t],
  )
  const featureColumns = useMemo<ColumnsType<FeatureCostRow>>(
    () => [
      { title: 'Feature', dataIndex: 'feature', key: 'feature' },
      { title: t('labels.calls'), dataIndex: 'calls', key: 'calls', align: 'right' },
      { title: t('labels.cost_usd'), dataIndex: 'cost_usd', key: 'cost', align: 'right' },
    ],
    [t],
  )

  return (
    <Space direction="vertical" size="large" style={{ width: '100%', padding: 16 }}>
      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
        <div>
          <Typography.Title level={3} style={{ margin: 0 }}>
            {t('title')}
          </Typography.Title>
          <Typography.Text type="secondary">{t('subtitle')}</Typography.Text>
        </div>
        <Radio.Group
          value={days}
          onChange={(e) => setDays(e.target.value)}
          buttonStyle="solid"
          optionType="button"
        >
          <Radio.Button value={7}>{t('range.7d')}</Radio.Button>
          <Radio.Button value={30}>{t('range.30d')}</Radio.Button>
          <Radio.Button value={90}>{t('range.90d')}</Radio.Button>
        </Radio.Group>
      </Space>

      {loading && !bundle.sales && (
        <div style={{ padding: 80, textAlign: 'center' }}>
          <Spin size="large" />
        </div>
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title={t('cards.sales_trend')} size="small" loading={loading}>
            <div style={{ height: 240 }}>
              {bundle.sales && bundle.sales.points.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={lineData(bundle.sales.points)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="value" stroke="#1677ff" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <Empty description={t('labels.no_data')} />
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={t('cards.purchase_trend')} size="small" loading={loading}>
            <div style={{ height: 240 }}>
              {bundle.purchase && bundle.purchase.points.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={lineData(bundle.purchase.points)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="value" stroke="#13c2c2" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <Empty description={t('labels.no_data')} />
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={t('cards.top_skus')} size="small" loading={loading}>
            <Table
              size="small"
              rowKey="id"
              pagination={false}
              dataSource={bundle.topSkus?.rows ?? []}
              columns={skuColumns}
              locale={{ emptyText: t('labels.no_data') }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={t('cards.top_suppliers')} size="small" loading={loading}>
            <Table
              size="small"
              rowKey="id"
              pagination={false}
              dataSource={bundle.topSuppliers?.rows ?? []}
              columns={supplierColumns}
              locale={{ emptyText: t('labels.no_data') }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={t('cards.top_customers')} size="small" loading={loading}>
            <Table
              size="small"
              rowKey="id"
              pagination={false}
              dataSource={bundle.topCustomers?.rows ?? []}
              columns={customerColumns}
              locale={{ emptyText: t('labels.no_data') }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={t('cards.inventory_turnover')} size="small" loading={loading}>
            <Table
              size="small"
              rowKey="sku_id"
              pagination={false}
              dataSource={bundle.turnover?.rows ?? []}
              columns={turnoverColumns}
              locale={{ emptyText: t('labels.no_data') }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={t('cards.warehouse_distribution')} size="small" loading={loading}>
            <div style={{ height: 260 }}>
              {bundle.warehouse && bundle.warehouse.rows.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={bundle.warehouse.rows.map((r) => ({
                      name: r.warehouse_code,
                      value: Number.parseFloat(r.on_hand_value),
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#722ed1" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Empty description={t('labels.no_data')} />
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={t('cards.category_share')} size="small" loading={loading}>
            <div style={{ height: 260 }}>
              {bundle.category && bundle.category.rows.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={bundle.category.rows.map((r) => ({
                        name: r.category_name,
                        value: Number.parseFloat(r.amount),
                      }))}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      label
                    >
                      {bundle.category.rows.map((_, idx) => (
                        <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <Empty description={t('labels.no_data')} />
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={t('cards.einvoice_status')} size="small" loading={loading}>
            <div style={{ height: 260 }}>
              {bundle.einvoice && bundle.einvoice.rows.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={bundle.einvoice.rows.map((r) => ({ name: r.status, value: r.count }))}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      label
                    >
                      {bundle.einvoice.rows.map((_, idx) => (
                        <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <Empty description={t('labels.no_data')} />
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={t('cards.ai_cost')} size="small" loading={loading}>
            <div style={{ height: 200 }}>
              {bundle.aiCost && bundle.aiCost.series.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={lineData(bundle.aiCost.series)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#52c41a" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Empty description={t('labels.no_data')} />
              )}
            </div>
            <Table
              size="small"
              rowKey="feature"
              pagination={false}
              dataSource={bundle.aiCost?.by_feature ?? []}
              columns={featureColumns}
              locale={{ emptyText: t('labels.no_data') }}
              style={{ marginTop: 12 }}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
