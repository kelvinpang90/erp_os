import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import { Badge, Button, Card, Empty, Space, Spin, Tabs, Tag, Typography } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { axiosInstance } from '../../api/client'

interface SKUDetail {
  id: number
  code: string
  barcode?: string
  name: string
  name_zh?: string
  description?: string
  brand?: { code: string; name: string }
  category?: { code: string; name: string }
  base_uom?: { code: string; name: string }
  tax_rate?: { code: string; name: string; rate: string }
  unit_price_excl_tax: string
  unit_price_incl_tax: string
  currency: string
  costing_method: string
  last_cost?: string
  safety_stock: string
  reorder_point: string
  reorder_qty: string
  track_batch: boolean
  track_expiry: boolean
  track_serial: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

interface MovementRow {
  id: number
  movement_type: string
  quantity: string
  unit_cost?: string | null
  avg_cost_after?: string | null
  occurred_at: string
}

interface MovementListResponse {
  items: MovementRow[]
  total: number
}

interface CostPoint {
  date: string
  avgCost: number
  qty: number
  movementType: string
}

export default function SKUDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation('inventory')
  const [sku, setSku] = useState<SKUDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [movements, setMovements] = useState<MovementRow[] | null>(null)
  const [movementsLoading, setMovementsLoading] = useState(false)

  useEffect(() => {
    if (!id) return
    axiosInstance
      .get(`/skus/${id}`)
      .then((res) => setSku(res.data))
      .catch(() => navigate('/skus'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  const loadMovements = () => {
    if (!id || movements !== null) return
    setMovementsLoading(true)
    axiosInstance
      .get<MovementListResponse>(`/inventory/movements?sku_id=${id}&page_size=200&page=1`)
      .then((res) => setMovements(res.data.items))
      .catch(() => setMovements([]))
      .finally(() => setMovementsLoading(false))
  }

  const costTrendData = useMemo<CostPoint[]>(() => {
    if (!movements) return []
    return movements
      .filter((m) => m.avg_cost_after !== null && m.avg_cost_after !== undefined)
      .slice()
      .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
      .map((m) => ({
        date: new Date(m.occurred_at).toLocaleDateString('en-MY'),
        avgCost: parseFloat(m.avg_cost_after as string),
        qty: parseFloat(m.quantity),
        movementType: m.movement_type,
      }))
  }, [movements])

  if (loading) {
    return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
  }
  if (!sku) return null

  const overviewTab = (
    <ProDescriptions<SKUDetail> column={2} dataSource={sku}>
      <ProDescriptions.Item label="Status">
        <Badge
          status={sku.is_active ? 'success' : 'default'}
          text={sku.is_active ? 'Active' : 'Inactive'}
        />
      </ProDescriptions.Item>
      <ProDescriptions.Item label="Code">{sku.code}</ProDescriptions.Item>
      <ProDescriptions.Item label="Name">{sku.name}</ProDescriptions.Item>
      {sku.name_zh && <ProDescriptions.Item label="Name (ZH)">{sku.name_zh}</ProDescriptions.Item>}
      {sku.barcode && <ProDescriptions.Item label="Barcode">{sku.barcode}</ProDescriptions.Item>}
      <ProDescriptions.Item label="Brand">{sku.brand?.name ?? '—'}</ProDescriptions.Item>
      <ProDescriptions.Item label="Category">{sku.category?.name ?? '—'}</ProDescriptions.Item>
      <ProDescriptions.Item label="Base UOM">{sku.base_uom?.code ?? '—'}</ProDescriptions.Item>
      <ProDescriptions.Item label="Tax Rate">
        {sku.tax_rate ? `${sku.tax_rate.code} (${sku.tax_rate.rate}%)` : '—'}
      </ProDescriptions.Item>
      <ProDescriptions.Item label="Price (excl. tax)">
        {sku.currency} {parseFloat(sku.unit_price_excl_tax).toFixed(4)}
      </ProDescriptions.Item>
      <ProDescriptions.Item label="Price (incl. tax)">
        {sku.currency} {parseFloat(sku.unit_price_incl_tax).toFixed(4)}
      </ProDescriptions.Item>
      <ProDescriptions.Item label="Costing Method">
        <Tag>{sku.costing_method}</Tag>
      </ProDescriptions.Item>
      {sku.last_cost && (
        <ProDescriptions.Item label="Last Cost">
          {sku.currency} {parseFloat(sku.last_cost).toFixed(4)}
        </ProDescriptions.Item>
      )}
      <ProDescriptions.Item label="Safety Stock">{sku.safety_stock}</ProDescriptions.Item>
      <ProDescriptions.Item label="Reorder Point">{sku.reorder_point}</ProDescriptions.Item>
      <ProDescriptions.Item label="Reorder Qty">{sku.reorder_qty}</ProDescriptions.Item>
      <ProDescriptions.Item label="Tracking">
        <Space>
          {sku.track_batch && <Tag color="blue">Batch</Tag>}
          {sku.track_expiry && <Tag color="orange">Expiry</Tag>}
          {sku.track_serial && <Tag color="purple">Serial</Tag>}
          {!sku.track_batch && !sku.track_expiry && !sku.track_serial && '—'}
        </Space>
      </ProDescriptions.Item>
      <ProDescriptions.Item label="Created">
        {new Date(sku.created_at).toLocaleString()}
      </ProDescriptions.Item>
      <ProDescriptions.Item label="Updated">
        {new Date(sku.updated_at).toLocaleString()}
      </ProDescriptions.Item>
    </ProDescriptions>
  )

  const costTab = (
    <Spin spinning={movementsLoading}>
      {costTrendData.length > 0 ? (
        <>
          <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
            {t('costTrend.title')}
          </Typography.Paragraph>
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={costTrendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="date" />
              <YAxis tickFormatter={(v) => Number(v).toFixed(2)} />
              <ChartTooltip
                formatter={(value: number, name: string, props) => {
                  if (name === 'avgCost') {
                    return [`${sku.currency} ${value.toFixed(4)}`, t('costTrend.axisCost')]
                  }
                  return [
                    value,
                    `${t('costTrend.tooltipMovementType')}: ${props.payload.movementType}`,
                  ]
                }}
              />
              <Line
                type="monotone"
                dataKey="avgCost"
                stroke="#1677ff"
                strokeWidth={2}
                dot={{ r: 3 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </>
      ) : (
        !movementsLoading && <Empty description={t('costTrend.empty')} />
      )}
    </Spin>
  )

  return (
    <Card
      title={
        <Space>
          <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/skus')} />
          {sku.code} — {sku.name}
        </Space>
      }
      extra={
        <Button icon={<EditOutlined />} onClick={() => navigate(`/skus/${id}/edit`)}>
          Edit
        </Button>
      }
    >
      <Tabs
        defaultActiveKey="overview"
        onChange={(key) => {
          if (key === 'cost') loadMovements()
        }}
        items={[
          { key: 'overview', label: 'Overview', children: overviewTab },
          { key: 'cost', label: t('costTrend.title'), children: costTab },
        ]}
      />
    </Card>
  )
}
