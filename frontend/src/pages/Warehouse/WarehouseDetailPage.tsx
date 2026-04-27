import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import { Badge, Button, Card, Space, Spin, Tag } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'

const TYPE_COLORS: Record<string, string> = {
  MAIN: 'gold',
  BRANCH: 'blue',
  TRANSIT: 'cyan',
  QUARANTINE: 'red',
}

interface WarehouseDetail {
  id: number
  code: string
  name: string
  type: 'MAIN' | 'BRANCH' | 'TRANSIT' | 'QUARANTINE'
  address_line1?: string
  address_line2?: string
  city?: string
  state?: string
  postcode?: string
  country: string
  phone?: string
  manager_user_id?: number
  manager_name?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export default function WarehouseDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation('warehouse')
  const [warehouse, setWarehouse] = useState<WarehouseDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    axiosInstance
      .get(`/warehouses/${id}`)
      .then((res) => setWarehouse(res.data))
      .catch(() => navigate('/settings/warehouses'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  if (loading) return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
  if (!warehouse) return null

  const address = [warehouse.address_line1, warehouse.address_line2, warehouse.city, warehouse.state, warehouse.postcode, warehouse.country]
    .filter(Boolean)
    .join(', ')

  return (
    <Card
      title={
        <Space>
          <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/settings/warehouses')} />
          {warehouse.code} — {warehouse.name}
          <Tag color={TYPE_COLORS[warehouse.type]}>{warehouse.type}</Tag>
        </Space>
      }
      extra={
        <Button icon={<EditOutlined />} onClick={() => navigate(`/settings/warehouses/${id}/edit`)}>
          Edit
        </Button>
      }
    >
      <ProDescriptions column={2}>
        <ProDescriptions.Item label="Status">
          <Badge status={warehouse.is_active ? 'success' : 'default'} text={warehouse.is_active ? 'Active' : 'Inactive'} />
        </ProDescriptions.Item>
        <ProDescriptions.Item label={t('type')}>
          <Tag color={TYPE_COLORS[warehouse.type]}>
            {({ MAIN: t('type_main'), BRANCH: t('type_branch'), TRANSIT: t('type_transit'), QUARANTINE: t('type_quarantine') })[warehouse.type]}
          </Tag>
        </ProDescriptions.Item>
        <ProDescriptions.Item label={t('code')}>{warehouse.code}</ProDescriptions.Item>
        <ProDescriptions.Item label={t('name')}>{warehouse.name}</ProDescriptions.Item>
        <ProDescriptions.Item label={t('manager')}>{warehouse.manager_name || '—'}</ProDescriptions.Item>
        <ProDescriptions.Item label={t('phone')}>{warehouse.phone || '—'}</ProDescriptions.Item>
        <ProDescriptions.Item label={t('address')} span={2}>{address || '—'}</ProDescriptions.Item>
      </ProDescriptions>
    </Card>
  )
}
