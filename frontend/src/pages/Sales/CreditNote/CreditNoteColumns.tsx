import type { ProColumns } from '@ant-design/pro-components'
import { Tag } from 'antd'

type Translator = (key: string, opts?: Record<string, unknown>) => string

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

export function cnStatusLabel(t: Translator, status: string): string {
  // Reuses einvoice:status_* keys.
  return t(`status_${status}`, { defaultValue: status })
}

export function cnReasonLabel(t: Translator, reason: string): string {
  return t(`creditNote.reasons.${reason}`, { defaultValue: reason })
}

export function getCreditNoteColumns(t: Translator): ProColumns<CreditNoteRow>[] {
  return [
    {
      title: t('creditNote.columns.cnNo'),
      dataIndex: 'document_no',
      width: 160,
      fixed: 'left',
    },
    {
      title: t('status'),
      dataIndex: 'status',
      width: 130,
      valueType: 'select',
      valueEnum: {
        DRAFT: { text: cnStatusLabel(t, 'DRAFT') },
        SUBMITTED: { text: cnStatusLabel(t, 'SUBMITTED') },
        VALIDATED: { text: cnStatusLabel(t, 'VALIDATED') },
        FINAL: { text: cnStatusLabel(t, 'FINAL') },
        REJECTED: { text: cnStatusLabel(t, 'REJECTED') },
        CANCELLED: { text: cnStatusLabel(t, 'CANCELLED') },
      },
      render: (_, row) => (
        <Tag color={CN_STATUS_COLOR[row.status] ?? 'default'}>
          {cnStatusLabel(t, row.status)}
        </Tag>
      ),
    },
    {
      title: t('creditNote.columns.invoiceNo'),
      dataIndex: 'invoice_no',
      width: 160,
      hideInSearch: true,
      render: (val) => val || '—',
    },
    {
      title: t('customer'),
      dataIndex: 'customer_name',
      width: 200,
      hideInSearch: true,
      ellipsis: true,
    },
    {
      title: t('creditNote.columns.reason'),
      dataIndex: 'reason',
      width: 160,
      hideInSearch: true,
      render: (_, row) => cnReasonLabel(t, row.reason),
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
      title: t('creditNote.columns.total'),
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
}
