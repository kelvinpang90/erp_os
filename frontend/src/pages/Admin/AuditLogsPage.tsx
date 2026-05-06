import type { ProColumns } from '@ant-design/pro-components'
import { Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'

interface AuditLogRow {
  id: number
  organization_id: number
  entity_type: string
  entity_id: number
  action: string
  actor_user_id: number | null
  actor_email: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  ip: string | null
  user_agent: string | null
  request_id: string | null
  occurred_at: string
}

const ACTION_COLORS: Record<string, string> = {
  CREATED: 'green',
  UPDATED: 'blue',
  DELETED: 'red',
  RESTORED: 'cyan',
  STATUS_CHANGED: 'geekblue',
  APPROVED: 'green',
  CANCELLED: 'volcano',
  SUBMITTED: 'gold',
  VALIDATED: 'green',
  REJECTED: 'red',
  FINALIZED: 'purple',
}

async function fetchLogs(params: {
  current?: number
  pageSize?: number
  entity_type?: string
  entity_id?: number
  action?: string
}) {
  const { current = 1, pageSize = 20, entity_type, entity_id, action } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  if (entity_type) query.set('entity_type', entity_type)
  if (entity_id) query.set('entity_id', String(entity_id))
  if (action) query.set('action', action)
  const res = await axiosInstance.get(`/audit/logs?${query}`)
  return res.data
}

export default function AuditLogsPage() {
  const { t } = useTranslation('admin')

  const columns: ProColumns<AuditLogRow>[] = [
    {
      title: t('audit.columns.occurred_at'),
      dataIndex: 'occurred_at',
      width: 170,
      hideInSearch: true,
      render: (_, row) => dayjs(row.occurred_at).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: t('audit.columns.entity_type'),
      dataIndex: 'entity_type',
      width: 110,
      valueType: 'select',
      valueEnum: {
        PO: { text: 'PO' },
        SO: { text: 'SO' },
        INVOICE: { text: 'INVOICE' },
        CN: { text: 'CN' },
        TRANSFER: { text: 'TRANSFER' },
        ADJUSTMENT: { text: 'ADJUSTMENT' },
      },
    },
    {
      title: t('audit.columns.entity_id'),
      dataIndex: 'entity_id',
      width: 80,
      valueType: 'digit',
    },
    {
      title: t('audit.columns.action'),
      dataIndex: 'action',
      width: 130,
      valueType: 'select',
      valueEnum: Object.fromEntries(Object.keys(ACTION_COLORS).map((k) => [k, { text: k }])),
      render: (_, row) => <Tag color={ACTION_COLORS[row.action] ?? 'default'}>{row.action}</Tag>,
    },
    {
      title: t('audit.columns.actor'),
      dataIndex: 'actor_email',
      width: 200,
      hideInSearch: true,
      render: (_, row) => row.actor_email ?? (row.actor_user_id ? `#${row.actor_user_id}` : '—'),
    },
    {
      title: t('audit.columns.diff'),
      hideInSearch: true,
      render: (_, row) => (
        <details>
          <summary style={{ cursor: 'pointer', color: '#1677ff' }}>
            {t('audit.show_diff')}
          </summary>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <pre style={preStyle}>
              <Typography.Text type="danger">before:</Typography.Text>
              {'\n'}
              {JSON.stringify(row.before ?? {}, null, 2)}
            </pre>
            <pre style={preStyle}>
              <Typography.Text type="success">after:</Typography.Text>
              {'\n'}
              {JSON.stringify(row.after ?? {}, null, 2)}
            </pre>
          </div>
        </details>
      ),
    },
    {
      title: t('audit.columns.request_id'),
      dataIndex: 'request_id',
      width: 230,
      hideInSearch: true,
      copyable: true,
      ellipsis: true,
      render: (_, row) => row.request_id ?? '—',
    },
  ]

  return (
    <ResourceListPage<AuditLogRow>
      title={t('audit.title')}
      columns={columns}
      fetchData={fetchLogs}
    />
  )
}

const preStyle: React.CSSProperties = {
  flex: 1,
  background: 'rgba(0,0,0,0.04)',
  padding: 8,
  margin: 0,
  fontSize: 12,
  overflow: 'auto',
  maxHeight: 200,
  borderRadius: 4,
}
