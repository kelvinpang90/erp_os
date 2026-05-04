import type { ProColumns } from '@ant-design/pro-components'
import { Badge, Tag } from 'antd'
import type { TFunction } from 'i18next'

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

export const buildSkuColumns = (t: TFunction): ProColumns<SKURow>[] => [
  {
    title: t('columns.code'),
    dataIndex: 'code',
    width: 120,
    fixed: 'left',
    copyable: true,
  },
  {
    title: t('columns.name'),
    dataIndex: 'name',
    ellipsis: true,
  },
  {
    title: t('columns.barcode'),
    dataIndex: 'barcode',
    hideInSearch: true,
    width: 130,
  },
  {
    title: t('columns.priceExclTax'),
    dataIndex: 'unit_price_excl_tax',
    hideInSearch: true,
    width: 140,
    render: (_, row) =>
      `${row.currency} ${parseFloat(row.unit_price_excl_tax).toFixed(2)}`,
  },
  {
    title: t('columns.safetyStock'),
    dataIndex: 'safety_stock',
    hideInSearch: true,
    width: 120,
    render: (val) => parseFloat(val as string).toFixed(2),
  },
  {
    title: t('columns.costing'),
    dataIndex: 'costing_method',
    hideInSearch: true,
    width: 140,
    render: (val) => <Tag>{val as string}</Tag>,
  },
  {
    title: t('columns.status'),
    dataIndex: 'is_active',
    width: 90,
    valueEnum: {
      true: { text: t('columns.active') },
      false: { text: t('columns.inactive') },
    },
    render: (_, row) => (
      <Badge
        status={row.is_active ? 'success' : 'default'}
        text={row.is_active ? t('columns.active') : t('columns.inactive')}
      />
    ),
  },
  {
    title: t('columns.created'),
    dataIndex: 'created_at',
    hideInSearch: true,
    width: 160,
    render: (val) => new Date(val as string).toLocaleDateString(),
  },
]
