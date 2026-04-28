import type { ProColumns } from '@ant-design/pro-components'

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

export const grColumns: ProColumns<GRRow>[] = [
  {
    title: 'GR Number',
    dataIndex: 'document_no',
    width: 150,
    fixed: 'left',
  },
  {
    title: 'PO Number',
    dataIndex: 'purchase_order_no',
    width: 150,
    hideInSearch: true,
  },
  {
    title: 'Receipt Date',
    dataIndex: 'receipt_date',
    width: 120,
    hideInSearch: true,
  },
  {
    title: 'Delivery Note',
    dataIndex: 'delivery_note_no',
    width: 140,
    hideInSearch: true,
    render: (val) => val ?? '—',
  },
  {
    title: 'Created',
    dataIndex: 'created_at',
    width: 160,
    hideInSearch: true,
    render: (val) => new Date(String(val)).toLocaleString('en-MY'),
  },
]
