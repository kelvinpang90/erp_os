import type { ProColumns } from '@ant-design/pro-components'
import { Badge, Tag } from 'antd'

export interface WarehouseRow {
  id: number
  code: string
  name: string
  type: 'MAIN' | 'BRANCH' | 'TRANSIT' | 'QUARANTINE'
  city?: string
  state?: string
  country: string
  phone?: string
  manager_name?: string
  is_active: boolean
  created_at: string
}

const TYPE_COLORS: Record<string, string> = {
  MAIN: 'gold',
  BRANCH: 'blue',
  TRANSIT: 'cyan',
  QUARANTINE: 'red',
}

export const warehouseColumns: ProColumns<WarehouseRow>[] = [
  {
    title: 'Code',
    dataIndex: 'code',
    width: 110,
    fixed: 'left',
  },
  {
    title: 'Name',
    dataIndex: 'name',
    ellipsis: true,
  },
  {
    title: 'Type',
    dataIndex: 'type',
    width: 110,
    hideInSearch: true,
    render: (val) => (
      <Tag color={TYPE_COLORS[String(val)] ?? 'default'}>{String(val)}</Tag>
    ),
  },
  {
    title: 'Location',
    width: 160,
    hideInSearch: true,
    render: (_, row) => [row.city, row.state].filter(Boolean).join(', ') || '—',
  },
  {
    title: 'Manager',
    dataIndex: 'manager_name',
    width: 140,
    ellipsis: true,
    hideInSearch: true,
    render: (val) => val || '—',
  },
  {
    title: 'Phone',
    dataIndex: 'phone',
    width: 130,
    hideInSearch: true,
    render: (val) => val || '—',
  },
  {
    title: 'Status',
    dataIndex: 'is_active',
    width: 90,
    hideInSearch: true,
    render: (val) => (
      <Badge status={val ? 'success' : 'default'} text={val ? 'Active' : 'Inactive'} />
    ),
  },
]
