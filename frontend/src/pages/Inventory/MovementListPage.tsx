import type { ProColumns } from '@ant-design/pro-components'
import { Tag } from 'antd'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'

interface MovementRow {
  id: number
  sku_id: number
  sku_code: string
  sku_name: string
  warehouse_id: number
  warehouse_name: string
  movement_type: string
  quantity: string
  unit_cost?: string
  avg_cost_after?: string
  source_document_type: string
  source_document_id: number
  occurred_at: string
}

const MOVEMENT_COLOR: Record<string, string> = {
  PURCHASE_IN: 'cyan',
  PURCHASE_RETURN: 'red',
  SALES_OUT: 'orange',
  SALES_RETURN: 'cyan',
  TRANSFER_OUT: 'gold',
  TRANSFER_IN: 'gold',
  ADJUSTMENT_IN: 'green',
  ADJUSTMENT_OUT: 'red',
  RESERVE: 'purple',
  UNRESERVE: 'default',
  QUALITY_HOLD: 'magenta',
  QUALITY_RELEASE: 'default',
}

const TYPE_KEYS = [
  'PURCHASE_IN',
  'PURCHASE_RETURN',
  'SALES_OUT',
  'SALES_RETURN',
  'TRANSFER_OUT',
  'TRANSFER_IN',
  'ADJUSTMENT_IN',
  'ADJUSTMENT_OUT',
  'RESERVE',
  'UNRESERVE',
  'QUALITY_HOLD',
  'QUALITY_RELEASE',
] as const

const SOURCE_KEYS = [
  'PO',
  'SO',
  'GR',
  'DO',
  'CN',
  'TRANSFER',
  'ADJUSTMENT',
  'OPENING',
  'DEMO_RESET',
] as const

async function fetchMovements(params: {
  current?: number
  pageSize?: number
  movement_type?: string
  source_document_type?: string
  sku_id?: number
  warehouse_id?: number
  date_from?: string
  date_to?: string
}) {
  const { current = 1, pageSize = 20, ...rest } = params
  const query = new URLSearchParams({
    page: String(current),
    page_size: String(pageSize),
  })
  for (const [k, v] of Object.entries(rest)) {
    if (v !== undefined && v !== null && v !== '') query.set(k, String(v))
  }
  const res = await axiosInstance.get(`/inventory/movements?${query}`)
  return res.data
}

export default function MovementListPage() {
  const { t } = useTranslation('stock_movement')

  const columns: ProColumns<MovementRow>[] = [
    {
      title: t('occurred_at'),
      dataIndex: 'occurred_at',
      width: 160,
      hideInSearch: true,
      render: (val) => new Date(String(val)).toLocaleString('en-MY'),
    },
    {
      title: t('movement_type'),
      dataIndex: 'movement_type',
      width: 140,
      valueType: 'select',
      valueEnum: Object.fromEntries(
        TYPE_KEYS.map((k) => [k, { text: t(`type_${k}`) }]),
      ),
      render: (val) => (
        <Tag color={MOVEMENT_COLOR[String(val)] ?? 'default'}>
          {t(`type_${String(val)}`)}
        </Tag>
      ),
    },
    {
      title: t('source_document'),
      dataIndex: 'source_document_type',
      width: 130,
      valueType: 'select',
      valueEnum: Object.fromEntries(
        SOURCE_KEYS.map((k) => [k, { text: t(`source_${k}`) }]),
      ),
      render: (val, row) =>
        `${t(`source_${String(val)}`)} #${row.source_document_id}`,
    },
    {
      title: t('warehouse'),
      dataIndex: 'warehouse_id',
      width: 150,
      hideInSearch: true,
      render: (_, row) => row.warehouse_name || `#${row.warehouse_id}`,
    },
    {
      title: t('sku'),
      dataIndex: 'sku_id',
      width: 260,
      valueType: 'digit',
      render: (_, row) =>
        row.sku_code ? `${row.sku_code} — ${row.sku_name}` : `#${row.sku_id}`,
    },
    {
      title: t('quantity'),
      dataIndex: 'quantity',
      width: 100,
      align: 'right',
      hideInSearch: true,
    },
    {
      title: t('unit_cost'),
      dataIndex: 'unit_cost',
      width: 110,
      align: 'right',
      hideInSearch: true,
      render: (val: string | undefined) => val ?? '—',
    },
    {
      title: t('avg_cost_after'),
      dataIndex: 'avg_cost_after',
      width: 130,
      align: 'right',
      hideInSearch: true,
      render: (val: string | undefined) => val ?? '—',
    },
    {
      title: t('filter.date_from'),
      dataIndex: 'date_from',
      valueType: 'date',
      hideInTable: true,
    },
    {
      title: t('filter.date_to'),
      dataIndex: 'date_to',
      valueType: 'date',
      hideInTable: true,
    },
    {
      title: t('warehouse'),
      dataIndex: 'warehouse_id_filter',
      hideInTable: true,
      valueType: 'digit',
    },
  ]

  return (
    <ResourceListPage<MovementRow>
      title={t('title')}
      columns={columns}
      fetchData={fetchMovements}
    />
  )
}
