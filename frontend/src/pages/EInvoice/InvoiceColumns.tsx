import type { ProColumns } from '@ant-design/pro-components'
import { Tag } from 'antd'

export interface InvoiceRow {
  id: number
  document_no: string
  status: string
  invoice_type: string
  sales_order_id?: number
  sales_order_no?: string
  customer_id: number
  customer_name?: string
  business_date: string
  due_date?: string
  currency: string
  total_incl_tax: string
  paid_amount: string
  uin?: string | null
  submitted_at?: string | null
  validated_at?: string | null
  finalized_at?: string | null
  rejected_at?: string | null
  created_at: string
}

export const STATUS_COLOR: Record<string, string> = {
  DRAFT: 'default',
  SUBMITTED: 'blue',
  VALIDATED: 'gold',
  FINAL: 'green',
  REJECTED: 'red',
  CANCELLED: 'default',
}

export const STATUS_LABEL: Record<string, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  VALIDATED: 'Validated (in 72h window)',
  FINAL: 'Final',
  REJECTED: 'Rejected',
  CANCELLED: 'Cancelled',
}

export const invoiceColumns: ProColumns<InvoiceRow>[] = [
  {
    title: 'Invoice No',
    dataIndex: 'document_no',
    width: 160,
    fixed: 'left',
  },
  {
    title: 'Status',
    dataIndex: 'status',
    width: 200,
    valueType: 'select',
    valueEnum: {
      DRAFT: { text: STATUS_LABEL.DRAFT },
      SUBMITTED: { text: STATUS_LABEL.SUBMITTED },
      VALIDATED: { text: STATUS_LABEL.VALIDATED },
      FINAL: { text: STATUS_LABEL.FINAL },
      REJECTED: { text: STATUS_LABEL.REJECTED },
      CANCELLED: { text: STATUS_LABEL.CANCELLED },
    },
    render: (val) => (
      <Tag color={STATUS_COLOR[String(val)] ?? 'default'}>
        {STATUS_LABEL[String(val)] ?? String(val)}
      </Tag>
    ),
  },
  {
    title: 'SO',
    dataIndex: 'sales_order_no',
    width: 130,
    hideInSearch: true,
    render: (val) => val || '—',
  },
  {
    title: 'Customer',
    dataIndex: 'customer_name',
    width: 180,
    hideInSearch: true,
    ellipsis: true,
  },
  {
    title: 'Business Date',
    dataIndex: 'business_date',
    width: 120,
    hideInSearch: true,
  },
  {
    title: 'UIN',
    dataIndex: 'uin',
    width: 180,
    hideInSearch: true,
    render: (val) => val ?? '—',
  },
  {
    title: 'Total',
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
    title: 'Validated',
    dataIndex: 'validated_at',
    width: 160,
    hideInSearch: true,
    render: (val) => (val ? new Date(String(val)).toLocaleString('en-MY') : '—'),
  },
]
