import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import { Badge, Button, Card, Space, Spin, Tag } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'

interface CustomerDetail {
  id: number
  code: string
  name: string
  name_zh?: string
  customer_type: 'B2B' | 'B2C'
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
}

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation('customer')
  const [customer, setCustomer] = useState<CustomerDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    axiosInstance
      .get(`/customers/${id}`)
      .then((res) => setCustomer(res.data))
      .catch(() => navigate('/sales/customers'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  if (loading) return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
  if (!customer) return null

  const isB2B = customer.customer_type === 'B2B'
  const address = [customer.address_line1, customer.address_line2, customer.city, customer.state, customer.postcode, customer.country]
    .filter(Boolean)
    .join(', ')

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/sales/customers')} />
            {customer.code} — {customer.name}
            <Tag color={isB2B ? 'blue' : 'green'}>{customer.customer_type}</Tag>
          </Space>
        }
        extra={
          <Button icon={<EditOutlined />} onClick={() => navigate(`/sales/customers/${id}/edit`)}>
            Edit
          </Button>
        }
      >
        <ProDescriptions column={2}>
          <ProDescriptions.Item label="Status">
            <Badge status={customer.is_active ? 'success' : 'default'} text={customer.is_active ? 'Active' : 'Inactive'} />
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('customer_type')}>
            <Tag color={isB2B ? 'blue' : 'green'}>{isB2B ? t('type_b2b') : t('type_b2c')}</Tag>
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('code')}>{customer.code}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('name')}>{customer.name}</ProDescriptions.Item>
          {customer.name_zh && <ProDescriptions.Item label={t('name_zh')}>{customer.name_zh}</ProDescriptions.Item>}
          <ProDescriptions.Item label={t('contact_person')}>{customer.contact_person || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('email')}>{customer.email || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('phone')}>{customer.phone || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('address')} span={2}>{address || '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('currency')}>{customer.currency}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('payment_terms_days')}>{customer.payment_terms_days} days</ProDescriptions.Item>
          <ProDescriptions.Item label={t('credit_limit')}>
            {customer.currency} {parseFloat(customer.credit_limit).toLocaleString('en-MY', { minimumFractionDigits: 2 })}
          </ProDescriptions.Item>
          {customer.notes && <ProDescriptions.Item label="Notes" span={2}>{customer.notes}</ProDescriptions.Item>}
        </ProDescriptions>
      </Card>

      {/* B2B 企业信息块 — 仅当 customer_type === B2B 时显示 */}
      {isB2B && (
        <Card title={t('business_info')}>
          <ProDescriptions column={2}>
            <ProDescriptions.Item label={t('registration_no')}>{customer.registration_no || '—'}</ProDescriptions.Item>
            <ProDescriptions.Item label={t('tin')}>{customer.tin || '—'}</ProDescriptions.Item>
            <ProDescriptions.Item label={t('sst_registration_no')}>{customer.sst_registration_no || '—'}</ProDescriptions.Item>
            <ProDescriptions.Item label={t('msic_code')}>{customer.msic_code || '—'}</ProDescriptions.Item>
          </ProDescriptions>
        </Card>
      )}
    </Space>
  )
}
