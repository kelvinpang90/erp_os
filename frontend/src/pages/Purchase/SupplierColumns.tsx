import type { ProColumns } from '@ant-design/pro-components'
import { Badge } from 'antd'

type Translator = (key: string, opts?: Record<string, unknown>) => string

export interface SupplierRow {
  id: number
  code: string
  name: string
  name_zh?: string
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

export function getSupplierColumns(t: Translator, tCommon: Translator): ProColumns<SupplierRow>[] {
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
      title: t('columns.terms'),
      dataIndex: 'payment_terms_days',
      width: 80,
      hideInSearch: true,
      render: (val) => `${val}d`,
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
