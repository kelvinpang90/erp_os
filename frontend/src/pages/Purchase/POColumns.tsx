import type { ProColumns } from '@ant-design/pro-components'
import { Tag } from 'antd'

type Translator = (key: string, opts?: Record<string, unknown>) => string

export interface PORow {
  id: number
  document_no: string
  status: string
  supplier_id: number
  warehouse_id: number
  business_date: string
  expected_date?: string
  currency: string
  subtotal_excl_tax: string
  tax_amount: string
  total_incl_tax: string
  payment_terms_days: number
  created_at: string
}

const STATUS_COLOR: Record<string, string> = {
  DRAFT: 'default',
  CONFIRMED: 'blue',
  PARTIAL_RECEIVED: 'orange',
  FULLY_RECEIVED: 'green',
  CANCELLED: 'red',
}

export function getPoColumns(t: Translator): ProColumns<PORow>[] {
  return [
    {
      title: t('document_no'),
      dataIndex: 'document_no',
      width: 150,
      fixed: 'left',
    },
    {
      title: t('status'),
      dataIndex: 'status',
      width: 140,
      hideInSearch: true,
      render: (val) => (
        <Tag color={STATUS_COLOR[String(val)] ?? 'default'}>
          {t(`status_${String(val)}`, { defaultValue: String(val) })}
        </Tag>
      ),
    },
    {
      title: t('business_date'),
      dataIndex: 'business_date',
      width: 110,
      hideInSearch: true,
    },
    {
      title: t('expected_date'),
      dataIndex: 'expected_date',
      width: 120,
      hideInSearch: true,
      render: (val) => val ?? '—',
    },
    {
      title: t('currency'),
      dataIndex: 'currency',
      width: 80,
      hideInSearch: true,
    },
    {
      title: t('total_incl_tax'),
      dataIndex: 'total_incl_tax',
      width: 150,
      hideInSearch: true,
      render: (val, row) =>
        `${row.currency} ${parseFloat(String(val)).toLocaleString('en-MY', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}`,
    },
    {
      title: t('columns.terms'),
      dataIndex: 'payment_terms_days',
      width: 80,
      hideInSearch: true,
      render: (val) => `${val}d`,
    },
    {
      title: t('columns.created'),
      dataIndex: 'created_at',
      width: 160,
      hideInSearch: true,
      render: (val) => new Date(String(val)).toLocaleString('en-MY'),
    },
  ]
}
