import type { ProColumns } from '@ant-design/pro-components'
import { Tag } from 'antd'

export interface CreditNoteRow {
  id: number
  document_no: string
  status: string
  invoice_id: number
  invoice_no?: string
  customer_id: number
  customer_name?: string
  business_date: string
  reason: string
  currency: string
  total_incl_tax: string
  uin?: string | null
  submitted_at?: string | null
  validated_at?: string | null
  created_at: string
}

export const CN_STATUS_COLOR: Record<string, string> = {
  DRAFT: 'default',
  SUBMITTED: 'blue',
  VALIDATED: 'gold',
  FINAL: 'green',
  REJECTED: 'red',
  CANCELLED: 'default',
}

export const CN_STATUS_LABEL: Record<string, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  VALIDATED: 'Validated',
  FINAL: 'Final',
  REJECTED: 'Rejected',
  CANCELLED: 'Cancelled',
}

export const CN_REASON_LABEL: Record<string, string> = {
  RETURN: 'Return',
  DISCOUNT_ADJUSTMENT: 'Discount Adjustment',
  PRICE_CORRECTION: 'Price Correction',
  WRITE_OFF: 'Write-Off',
  OTHER: 'Other',
}

export const creditNoteColumns: ProColumns<CreditNoteRow>[] = [
  {
    title: 'CN No',
    dataIndex: 'document_no',
    width: 160,
    fixed: 'left',
  },
  {
    title: 'Status',
    dataIndex: 'status',
    width: 130,
    valueType: 'select',
    valueEnum: {
      DRAFT: { text: CN_STATUS_LABEL.DRAFT },
      SUBMITTED: { text: CN_STATUS_LABEL.SUBMITTED },
      VALIDATED: { text: CN_STATUS_LABEL.VALIDATED },
      FINAL: { text: CN_STATUS_LABEL.FINAL },
      REJECTED: { text: CN_STATUS_LABEL.REJECTED },
      CANCELLED: { text: CN_STATUS_LABEL.CANCELLED },
    },
    render: (_, row) => (
      <Tag color={CN_STATUS_COLOR[row.status] ?? 'default'}>
        {CN_STATUS_LABEL[row.status] ?? row.status}
      </Tag>
    ),
  },
  {
    title: 'Invoice No',
    dataIndex: 'invoice_no',
    width: 160,
    hideInSearch: true,
    render: (val) => val || '—',
  },
  {
    title: 'Customer',
    dataIndex: 'customer_name',
    width: 200,
    hideInSearch: true,
    ellipsis: true,
  },
  {
    title: 'Reason',
    dataIndex: 'reason',
    width: 160,
    hideInSearch: true,
    render: (_, row) => CN_REASON_LABEL[row.reason] ?? row.reason,
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
    width: 140,
    hideInSearch: true,
    render: (val, row) =>
      `${row.currency} ${parseFloat(String(val)).toLocaleString('en-MY', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`,
  },
]
