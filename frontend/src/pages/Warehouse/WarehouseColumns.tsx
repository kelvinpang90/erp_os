import type { ProColumns } from '@ant-design/pro-components'
import { Badge, Tag } from 'antd'
import type { TFunction } from 'i18next'

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

export const buildWarehouseColumns = (t: TFunction): ProColumns<WarehouseRow>[] => [
  {
    title: t('columns.code'),
    dataIndex: 'code',
    width: 110,
    fixed: 'left',
  },
  {
    title: t('columns.name'),
    dataIndex: 'name',
    ellipsis: true,
  },
  {
    title: t('columns.type'),
    dataIndex: 'type',
    width: 110,
    hideInSearch: true,
    render: (val) => (
      <Tag color={TYPE_COLORS[String(val)] ?? 'default'}>{t(`type_label.${String(val)}`)}</Tag>
    ),
  },
  {
    title: t('columns.location'),
    width: 160,
    hideInSearch: true,
    render: (_, row) => [row.city, row.state].filter(Boolean).join(', ') || '—',
  },
  {
    title: t('columns.manager'),
    dataIndex: 'manager_name',
    width: 140,
    ellipsis: true,
    hideInSearch: true,
    render: (val) => val || '—',
  },
  {
    title: t('columns.phone'),
    dataIndex: 'phone',
    width: 130,
    hideInSearch: true,
    render: (val) => val || '—',
  },
  {
    title: t('columns.status'),
    dataIndex: 'is_active',
    width: 90,
    hideInSearch: true,
    render: (val) => (
      <Badge status={val ? 'success' : 'default'} text={val ? t('active') : t('inactive')} />
    ),
  },
]
