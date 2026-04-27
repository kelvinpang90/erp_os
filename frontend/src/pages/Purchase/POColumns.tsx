import type { ProColumns } from '@ant-design/pro-components'
import { Tag } from 'antd'

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

const STATUS_LABEL: Record<string, string> = {
  DRAFT: 'Draft',
  CONFIRMED: 'Confirmed',
  PARTIAL_RECEIVED: 'Partial Received',
  FULLY_RECEIVED: 'Fully Received',
  CANCELLED: 'Cancelled',
}

export const poColumns: ProColumns<PORow>[] = [
  {
    title: 'PO Number',
    dataIndex: 'document_no',
    width: 150,
    fixed: 'left',
  },
  {
    title: 'Status',
    dataIndex: 'status',
    width: 140,
    hideInSearch: true,
    render: (val) => (
      <Tag color={STATUS_COLOR[String(val)] ?? 'default'}>
        {STATUS_LABEL[String(val)] ?? String(val)}
      </Tag>
    ),
  },
  {
    title: 'Order Date',
    dataIndex: 'business_date',
    width: 110,
    hideInSearch: true,
  },
  {
    title: 'Expected Date',
    dataIndex: 'expected_date',
    width: 120,
    hideInSearch: true,
    render: (val) => val ?? '—',
  },
  {
    title: 'Currency',
    dataIndex: 'currency',
    width: 80,
    hideInSearch: true,
  },
  {
    title: 'Total (incl. tax)',
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
    title: 'Terms',
    dataIndex: 'payment_terms_days',
    width: 80,
    hideInSearch: true,
    render: (val) => `${val}d`,
  },
  {
    title: 'Created',
    dataIndex: 'created_at',
    width: 160,
    hideInSearch: true,
    render: (val) => new Date(String(val)).toLocaleString('en-MY'),
  },
]
