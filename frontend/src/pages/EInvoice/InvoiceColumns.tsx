import type { ProColumns } from '@ant-design/pro-components'
import { Tag } from 'antd'

type Translator = (key: string, opts?: Record<string, unknown>) => string

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

export function statusLabel(t: Translator, status: string): string {
  return t(`status_${status}`, { defaultValue: status })
}

export function getInvoiceColumns(t: Translator): ProColumns<InvoiceRow>[] {
  return [
    {
      title: t('document_no'),
      dataIndex: 'document_no',
      width: 160,
      fixed: 'left',
    },
    {
      title: t('status'),
      dataIndex: 'status',
      width: 200,
      valueType: 'select',
      valueEnum: {
        DRAFT: { text: statusLabel(t, 'DRAFT') },
        SUBMITTED: { text: statusLabel(t, 'SUBMITTED') },
        VALIDATED: { text: statusLabel(t, 'VALIDATED') },
        FINAL: { text: statusLabel(t, 'FINAL') },
        REJECTED: { text: statusLabel(t, 'REJECTED') },
        CANCELLED: { text: statusLabel(t, 'CANCELLED') },
      },
      render: (_, row) => (
        <Tag color={STATUS_COLOR[row.status] ?? 'default'}>
          {statusLabel(t, row.status)}
        </Tag>
      ),
    },
    {
      title: t('columns.so'),
      dataIndex: 'sales_order_no',
      width: 130,
      hideInSearch: true,
      render: (val) => val || '—',
    },
    {
      title: t('customer'),
      dataIndex: 'customer_name',
      width: 180,
      hideInSearch: true,
      ellipsis: true,
    },
    {
      title: t('business_date'),
      dataIndex: 'business_date',
      width: 120,
      hideInSearch: true,
    },
    {
      title: t('uin'),
      dataIndex: 'uin',
      width: 180,
      hideInSearch: true,
      render: (val) => val ?? '—',
    },
    {
      title: t('columns.total'),
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
      title: t('columns.validated'),
      dataIndex: 'validated_at',
      width: 160,
      hideInSearch: true,
      render: (val) => (val ? new Date(String(val)).toLocaleString('en-MY') : '—'),
    },
  ]
}
