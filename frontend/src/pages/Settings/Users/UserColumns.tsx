import type { ProColumns } from '@ant-design/pro-components'
import { Badge, Tag } from 'antd'
import dayjs from 'dayjs'
import type { TFunction } from 'i18next'

export interface UserRow {
  id: number
  email: string
  full_name: string
  locale?: string
  theme?: string
  is_active: boolean
  last_login_at?: string | null
  role_codes: string[]
}

const ROLE_COLORS: Record<string, string> = {
  ADMIN: 'red',
  MANAGER: 'gold',
  SALES: 'blue',
  PURCHASER: 'green',
}

export const buildUserColumns = (t: TFunction): ProColumns<UserRow>[] => [
  {
    title: t('columns.email'),
    dataIndex: 'email',
    width: 220,
    fixed: 'left',
    copyable: true,
  },
  {
    title: t('columns.full_name'),
    dataIndex: 'full_name',
    ellipsis: true,
  },
  {
    title: t('columns.roles'),
    dataIndex: 'role_codes',
    width: 240,
    hideInSearch: true,
    render: (_, row) =>
      row.role_codes?.length
        ? row.role_codes.map((code) => (
            <Tag key={code} color={ROLE_COLORS[code] ?? 'default'} style={{ marginInlineEnd: 4 }}>
              {code}
            </Tag>
          ))
        : '—',
  },
  {
    title: t('columns.last_login'),
    dataIndex: 'last_login_at',
    width: 170,
    hideInSearch: true,
    render: (val) => (val ? dayjs(val as string).format('YYYY-MM-DD HH:mm') : t('never')),
  },
  {
    title: t('columns.status'),
    dataIndex: 'is_active',
    width: 100,
    hideInSearch: true,
    render: (val) => (
      <Badge status={val ? 'success' : 'default'} text={val ? t('active') : t('inactive')} />
    ),
  },
]
