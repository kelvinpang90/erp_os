import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import { Badge, Button, Card, Space, Spin, Tag } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
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

export default function SKUDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [sku, setSku] = useState<SKUDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    axiosInstance
      .get(`/skus/${id}`)
      .then((res) => setSku(res.data))
      .catch(() => navigate('/skus'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  if (loading) return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
  if (!sku) return null

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
      <ProDescriptions<SKUDetail> column={2} dataSource={sku}>
        <ProDescriptions.Item label="Status">
          <Badge status={sku.is_active ? 'success' : 'default'} text={sku.is_active ? 'Active' : 'Inactive'} />
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
        <ProDescriptions.Item label="Created">{new Date(sku.created_at).toLocaleString()}</ProDescriptions.Item>
        <ProDescriptions.Item label="Updated">{new Date(sku.updated_at).toLocaleString()}</ProDescriptions.Item>
      </ProDescriptions>
    </Card>
  )
}
