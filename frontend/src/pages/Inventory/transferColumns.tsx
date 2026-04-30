import type { ProColumns } from '@ant-design/pro-components'
import { Tag } from 'antd'
import i18n from '../../i18n'

export interface TransferRow {
  id: number
  document_no: string
  status: string
  from_warehouse_id: number
  to_warehouse_id: number
  business_date: string
  expected_arrival_date?: string
  actual_arrival_date?: string
  created_at: string
}

const STATUS_COLOR: Record<string, string> = {
  DRAFT: 'default',
  CONFIRMED: 'blue',
  IN_TRANSIT: 'gold',
  RECEIVED: 'green',
  CANCELLED: 'red',
}

const tt = (key: string) => i18n.t(key, { ns: 'stock_transfer' })

export const transferColumns: ProColumns<TransferRow>[] = [
  {
    title: tt('document_no'),
    dataIndex: 'document_no',
    width: 150,
    fixed: 'left',
  },
  {
    title: tt('status'),
    dataIndex: 'status',
    width: 130,
    valueType: 'select',
    valueEnum: {
      DRAFT: { text: tt('status_DRAFT') },
      CONFIRMED: { text: tt('status_CONFIRMED') },
      IN_TRANSIT: { text: tt('status_IN_TRANSIT') },
      RECEIVED: { text: tt('status_RECEIVED') },
      CANCELLED: { text: tt('status_CANCELLED') },
    },
    render: (val) => (
      <Tag color={STATUS_COLOR[String(val)] ?? 'default'}>
        {tt(`status_${String(val)}`)}
      </Tag>
    ),
  },
  {
    title: tt('from_warehouse'),
    dataIndex: 'from_warehouse_id',
    width: 120,
    hideInSearch: true,
    render: (val) => `#${val}`,
  },
  {
    title: tt('to_warehouse'),
    dataIndex: 'to_warehouse_id',
    width: 120,
    hideInSearch: true,
    render: (val) => `#${val}`,
  },
  {
    title: tt('business_date'),
    dataIndex: 'business_date',
    width: 110,
    hideInSearch: true,
  },
  {
    title: tt('expected_arrival_date'),
    dataIndex: 'expected_arrival_date',
    width: 130,
    hideInSearch: true,
    render: (val) => val ?? '—',
  },
  {
    title: tt('actual_arrival_date'),
    dataIndex: 'actual_arrival_date',
    width: 130,
    hideInSearch: true,
    render: (val) => val ?? '—',
  },
]
