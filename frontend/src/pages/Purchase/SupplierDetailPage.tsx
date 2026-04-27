import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import { Badge, Button, Card, Col, Row, Space, Spin, Statistic, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'

interface SupplierDetail {
  id: number
  code: string
  name: string
  name_zh?: string
  registration_no?: string
  tin?: string
  sst_registration_no?: string
  msic_code?: string
  contact_person?: string
  email?: string
  phone?: string
  address_line1?: string
  address_line2?: string
  city?: string
  state?: string
  postcode?: string
  country: string
  currency: string
  payment_terms_days: number
  credit_limit: string
  notes?: string
  is_active: boolean
  created_at: string
  updated_at: string
  po_stats?: {
    total_po_count: number
    total_po_amount: string
    last_po_date?: string
  }
}

export default function SupplierDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation('supplier')
  const [supplier, setSupplier] = useState<SupplierDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    axiosInstance
      .get(`/suppliers/${id}`)
      .then((res) => setSupplier(res.data))
      .catch(() => navigate('/purchase/suppliers'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  if (loading) return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
  if (!supplier) return null

  const address = [supplier.address_line1, supplier.address_line2, supplier.city, supplier.state, supplier.postcode, supplier.country]
    .filter(Boolean)
    .join(', ')

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/purchase/suppliers')} />
            {supplier.code} — {supplier.name}
          </Space>
        }
        extra={
          <Button icon={<EditOutlined />} onClick={() => navigate(`/purchase/suppliers/${id}/edit`)}>
            Edit
          </Button>
        }
      >
        <ProDescriptions column={2}>
          <ProDescriptions.Item label="Status">
            <Badge status={supplier.is_active ? 'success' : 'default'} text={supplier.is_active ? 'Active' : 'Inactive'} />
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('code')}>{supplier.code}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('name')}>{supplier.name}</ProDescriptions.Item>
          {supplier.name_zh && <ProDescriptions.Item label={t('name_zh')}>{supplier.name_zh}</ProDescriptions.Item>}
          <ProDescriptions.Item label={t('contact_person')}>{supplier.contact_person || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('email')}>{supplier.email || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('phone')}>{supplier.phone || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('registration_no')}>{supplier.registration_no || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('tin')}>{supplier.tin || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('sst_registration_no')}>{supplier.sst_registration_no || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('msic_code')}>{supplier.msic_code || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('address')} span={2}>{address || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('currency')}>{supplier.currency}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('payment_terms_days')}>{supplier.payment_terms_days} days</ProDescriptions.Item>
          <ProDescriptions.Item label={t('credit_limit')}>
            {supplier.currency} {parseFloat(supplier.credit_limit).toLocaleString('en-MY', { minimumFractionDigits: 2 })}
          </ProDescriptions.Item>
          {supplier.notes && <ProDescriptions.Item label="Notes" span={2}>{supplier.notes}</ProDescriptions.Item>}
        </ProDescriptions>
      </Card>

      <Card title={t('po_history')}>
        <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
          {t('po_history_placeholder')}
        </Typography.Text>
        <Row gutter={24}>
          <Col span={8}>
            <Statistic title={t('total_pos')} value={supplier.po_stats?.total_po_count ?? 0} />
          </Col>
          <Col span={8}>
            <Statistic
              title={t('total_amount')}
              value={parseFloat(supplier.po_stats?.total_po_amount ?? '0').toFixed(2)}
              prefix={supplier.currency}
            />
          </Col>
          <Col span={8}>
            <Statistic title={t('last_po_date')} value={supplier.po_stats?.last_po_date ?? '—'} />
          </Col>
        </Row>
      </Card>
    </Space>
  )
}
