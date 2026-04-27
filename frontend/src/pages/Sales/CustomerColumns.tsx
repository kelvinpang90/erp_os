import type { ProColumns } from '@ant-design/pro-components'
import { Badge, Tag } from 'antd'

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

export const customerColumns: ProColumns<CustomerRow>[] = [
  {
    title: 'Code',
    dataIndex: 'code',
    width: 120,
    fixed: 'left',
  },
  {
    title: 'Name',
    dataIndex: 'name',
    ellipsis: true,
  },
  {
    title: 'Type',
    dataIndex: 'customer_type',
    width: 90,
    hideInSearch: true,
    render: (val) => (
      <Tag color={val === 'B2B' ? 'blue' : 'green'}>{String(val)}</Tag>
    ),
  },
  {
    title: 'Contact',
    dataIndex: 'contact_person',
    width: 140,
    ellipsis: true,
    hideInSearch: true,
  },
  {
    title: 'Email',
    dataIndex: 'email',
    width: 180,
    ellipsis: true,
    hideInSearch: true,
  },
  {
    title: 'Phone',
    dataIndex: 'phone',
    width: 130,
    hideInSearch: true,
  },
  {
    title: 'Currency',
    dataIndex: 'currency',
    width: 80,
    hideInSearch: true,
  },
  {
    title: 'Credit Limit',
    dataIndex: 'credit_limit',
    width: 130,
    hideInSearch: true,
    render: (val, row) => `${row.currency} ${parseFloat(String(val)).toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
  },
  {
    title: 'Status',
    dataIndex: 'is_active',
    width: 90,
    hideInSearch: true,
    render: (val) => (
      <Badge status={val ? 'success' : 'default'} text={val ? 'Active' : 'Inactive'} />
    ),
  },
]
