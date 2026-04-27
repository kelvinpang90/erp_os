import type { ProColumns } from '@ant-design/pro-components'
import { Badge, Tag } from 'antd'

export interface SKURow {
  id: number
  code: string
  barcode?: string
  name: string
  name_zh?: string
  brand_id?: number
  category_id?: number
  unit_price_excl_tax: string
  currency: string
  costing_method: string
  safety_stock: string
  is_active: boolean
  created_at: string
}

export const skuColumns: ProColumns<SKURow>[] = [
  {
    title: 'Code',
    dataIndex: 'code',
    width: 120,
    fixed: 'left',
    copyable: true,
  },
  {
    title: 'Name',
    dataIndex: 'name',
    ellipsis: true,
  },
  {
    title: 'Barcode',
    dataIndex: 'barcode',
    hideInSearch: true,
    width: 130,
  },
  {
    title: 'Price (excl. tax)',
    dataIndex: 'unit_price_excl_tax',
    hideInSearch: true,
    width: 140,
    render: (_, row) =>
      `${row.currency} ${parseFloat(row.unit_price_excl_tax).toFixed(2)}`,
  },
  {
    title: 'Safety Stock',
    dataIndex: 'safety_stock',
    hideInSearch: true,
    width: 120,
    render: (val) => parseFloat(val as string).toFixed(2),
  },
  {
    title: 'Costing',
    dataIndex: 'costing_method',
    hideInSearch: true,
    width: 140,
    render: (val) => <Tag>{val as string}</Tag>,
  },
  {
    title: 'Status',
    dataIndex: 'is_active',
    width: 90,
    valueEnum: {
      true: { text: 'Active' },
      false: { text: 'Inactive' },
    },
    render: (_, row) => (
      <Badge
        status={row.is_active ? 'success' : 'default'}
        text={row.is_active ? 'Active' : 'Inactive'}
      />
    ),
  },
  {
    title: 'Created',
    dataIndex: 'created_at',
    hideInSearch: true,
    width: 160,
    render: (val) => new Date(val as string).toLocaleDateString(),
  },
]
