import type { ProColumns } from '@ant-design/pro-components'

type Translator = (key: string, opts?: Record<string, unknown>) => string

export interface GRRow {
  id: number
  document_no: string
  purchase_order_id: number
  purchase_order_no: string
  warehouse_id: number
  receipt_date: string
  delivery_note_no?: string | null
  received_by?: number | null
  created_at: string
}

export function getGrColumns(t: Translator): ProColumns<GRRow>[] {
  return [
    {
      title: t('document_no'),
      dataIndex: 'document_no',
      width: 150,
      fixed: 'left',
    },
    {
      title: t('purchase_order_no'),
      dataIndex: 'purchase_order_no',
      width: 150,
      hideInSearch: true,
    },
    {
      title: t('receipt_date'),
      dataIndex: 'receipt_date',
      width: 120,
      hideInSearch: true,
    },
    {
      title: t('columns.deliveryNote'),
      dataIndex: 'delivery_note_no',
      width: 140,
      hideInSearch: true,
      render: (val) => val ?? '—',
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
