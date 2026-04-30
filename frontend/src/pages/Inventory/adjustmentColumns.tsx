import type { ProColumns } from '@ant-design/pro-components'
import { Tag } from 'antd'
import i18n from '../../i18n'

export interface AdjustmentRow {
  id: number
  document_no: string
  status: string
  warehouse_id: number
  business_date: string
  reason: string
  approved_at?: string
  created_at: string
}

const STATUS_COLOR: Record<string, string> = {
  DRAFT: 'default',
  CONFIRMED: 'green',
  CANCELLED: 'red',
}

const tt = (key: string) => i18n.t(key, { ns: 'stock_adjustment' })

export const adjustmentColumns: ProColumns<AdjustmentRow>[] = [
  {
    title: tt('document_no'),
    dataIndex: 'document_no',
    width: 150,
    fixed: 'left',
  },
  {
    title: tt('status'),
    dataIndex: 'status',
    width: 120,
    valueType: 'select',
    valueEnum: {
      DRAFT: { text: tt('status_DRAFT') },
      CONFIRMED: { text: tt('status_CONFIRMED') },
      CANCELLED: { text: tt('status_CANCELLED') },
    },
    render: (val) => (
      <Tag color={STATUS_COLOR[String(val)] ?? 'default'}>
        {tt(`status_${String(val)}`)}
      </Tag>
    ),
  },
  {
    title: tt('warehouse'),
    dataIndex: 'warehouse_id',
    width: 100,
    hideInSearch: true,
    render: (val) => `#${val}`,
  },
  {
    title: tt('reason'),
    dataIndex: 'reason',
    width: 130,
    valueType: 'select',
    valueEnum: {
      PHYSICAL_COUNT: { text: tt('reason_PHYSICAL_COUNT') },
      DAMAGE: { text: tt('reason_DAMAGE') },
      THEFT: { text: tt('reason_THEFT') },
      CORRECTION: { text: tt('reason_CORRECTION') },
      EXPIRY: { text: tt('reason_EXPIRY') },
      OTHER: { text: tt('reason_OTHER') },
    },
    render: (val) => tt(`reason_${String(val)}`),
  },
  {
    title: tt('business_date'),
    dataIndex: 'business_date',
    width: 110,
    hideInSearch: true,
  },
  {
    title: tt('approved_at'),
    dataIndex: 'approved_at',
    width: 160,
    hideInSearch: true,
    render: (val) => (val ? new Date(String(val)).toLocaleString('en-MY') : '—'),
  },
]
