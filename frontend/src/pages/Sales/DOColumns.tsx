import type { ProColumns } from '@ant-design/pro-components'

export interface DORow {
  id: number
  document_no: string
  sales_order_id: number
  sales_order_no: string
  warehouse_id: number
  delivery_date: string
  shipping_method?: string | null
  tracking_no?: string | null
  delivered_by?: number | null
  created_at: string
}

export const doColumns: ProColumns<DORow>[] = [
  {
    title: 'DO Number',
    dataIndex: 'document_no',
    width: 150,
    fixed: 'left',
  },
  {
    title: 'SO Number',
    dataIndex: 'sales_order_no',
    width: 150,
    hideInSearch: true,
  },
  {
    title: 'Delivery Date',
    dataIndex: 'delivery_date',
    width: 120,
    hideInSearch: true,
  },
  {
    title: 'Shipping Method',
    dataIndex: 'shipping_method',
    width: 140,
    hideInSearch: true,
    render: (val) => val ?? '—',
  },
  {
    title: 'Tracking',
    dataIndex: 'tracking_no',
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
