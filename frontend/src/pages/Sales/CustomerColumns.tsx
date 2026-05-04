import type { ProColumns } from '@ant-design/pro-components'
import { Badge, Tag } from 'antd'

type Translator = (key: string, opts?: Record<string, unknown>) => string

export interface CustomerRow {
  id: number
  code: string
  name: string
  name_zh?: string
  customer_type: 'B2B' | 'B2C'
  contact_person?: string
  email?: string
  phone?: string
  country: string
  currency: string
  payment_terms_days: number
  credit_limit: string
  is_active: boolean
  created_at: string
}

export function getCustomerColumns(t: Translator, tCommon: Translator): ProColumns<CustomerRow>[] {
  return [
    {
      title: t('code'),
      dataIndex: 'code',
      width: 120,
      fixed: 'left',
    },
    {
      title: t('name'),
      dataIndex: 'name',
      ellipsis: true,
    },
    {
      title: t('columns.type'),
      dataIndex: 'customer_type',
      width: 90,
      hideInSearch: true,
      render: (val) => (
        <Tag color={val === 'B2B' ? 'blue' : 'green'}>{String(val)}</Tag>
      ),
    },
    {
      title: t('columns.contact'),
      dataIndex: 'contact_person',
      width: 140,
      ellipsis: true,
      hideInSearch: true,
    },
    {
      title: t('email'),
      dataIndex: 'email',
      width: 180,
      ellipsis: true,
      hideInSearch: true,
    },
    {
      title: t('phone'),
      dataIndex: 'phone',
      width: 130,
      hideInSearch: true,
    },
    {
      title: t('currency'),
      dataIndex: 'currency',
      width: 80,
      hideInSearch: true,
    },
    {
      title: t('credit_limit'),
      dataIndex: 'credit_limit',
      width: 130,
      hideInSearch: true,
      render: (val, row) => `${row.currency} ${parseFloat(String(val)).toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
    },
    {
      title: tCommon('status'),
      dataIndex: 'is_active',
      width: 90,
      hideInSearch: true,
      render: (val) => (
        <Badge status={val ? 'success' : 'default'} text={val ? tCommon('active') : tCommon('inactive')} />
      ),
    },
  ]
}
