import type { ProColumns } from '@ant-design/pro-components'

type Translator = (key: string, opts?: Record<string, unknown>) => string

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

export function getDoColumns(t: Translator): ProColumns<DORow>[] {
  return [
    {
      title: t('document_no'),
      dataIndex: 'document_no',
      width: 150,
      fixed: 'left',
    },
    {
      title: t('sales_order_no'),
      dataIndex: 'sales_order_no',
      width: 150,
      hideInSearch: true,
    },
    {
      title: t('delivery_date'),
      dataIndex: 'delivery_date',
      width: 120,
      hideInSearch: true,
    },
    {
      title: t('shipping_method'),
      dataIndex: 'shipping_method',
      width: 140,
      hideInSearch: true,
      render: (val) => val ?? '—',
    },
    {
      title: t('columns.tracking'),
      dataIndex: 'tracking_no',
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
