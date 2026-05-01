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

/**
 * Build the column list for the adjustment list page. Pass an empty
 * `warehouseMap` while it's still loading; cells fall back to `#<id>`.
 */
export function getAdjustmentColumns(
  warehouseMap: Map<number, string>,
): ProColumns<AdjustmentRow>[] {
  const renderWarehouse = (id: number | undefined) => {
    if (id === undefined || id === null) return '—'
    return warehouseMap.get(id) ?? `#${id}`
  }

  return [
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
      // Read row.status, not the val arg — valueEnum has already wrapped it.
      render: (_, row) => (
        <Tag color={STATUS_COLOR[row.status] ?? 'default'}>
          {tt(`status_${row.status}`)}
        </Tag>
      ),
    },
    {
      title: tt('warehouse'),
      dataIndex: 'warehouse_id',
      width: 160,
      hideInSearch: true,
      render: (_, row) => renderWarehouse(row.warehouse_id),
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
      render: (_, row) => tt(`reason_${row.reason}`),
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
}
