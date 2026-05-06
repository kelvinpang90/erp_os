import { CheckOutlined } from '@ant-design/icons'
import { Button, Drawer, Empty, List, Space, Spin, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  useNotificationStore,
  type NotificationItem,
  type NotificationSeverity,
} from '../../stores/notificationStore'

const SEVERITY_COLOR: Record<NotificationSeverity, string> = {
  INFO: 'blue',
  SUCCESS: 'green',
  WARNING: 'orange',
  ERROR: 'red',
  CRITICAL: 'magenta',
}

interface Props {
  open: boolean
  onClose: () => void
}

export default function NotificationDrawer({ open, onClose }: Props) {
  const { t } = useTranslation('notification')
  const navigate = useNavigate()
  const items = useNotificationStore((s) => s.items)
  const loading = useNotificationStore((s) => s.loading)
  const fetchList = useNotificationStore((s) => s.fetchList)
  const markRead = useNotificationStore((s) => s.markRead)
  const markAllRead = useNotificationStore((s) => s.markAllRead)

  useEffect(() => {
    if (open) void fetchList()
  }, [open, fetchList])

  const renderTitle = (n: NotificationItem) => {
    if (n.i18n_key) {
      const params = (n.i18n_params ?? {}) as Record<string, unknown>
      return t(n.i18n_key, { ...params, defaultValue: n.title })
    }
    return n.title
  }

  const handleClick = async (n: NotificationItem) => {
    if (!n.is_read) {
      try {
        await markRead(n.id)
      } catch {
        /* ignore */
      }
    }
    if (n.action_url) {
      onClose()
      navigate(n.action_url.replace(/^\/app/, ''))
    }
  }

  return (
    <Drawer
      title={t('title')}
      placement="right"
      width={400}
      open={open}
      onClose={onClose}
      extra={
        items.some((n) => !n.is_read) ? (
          <Button size="small" type="link" onClick={() => void markAllRead()}>
            {t('markAllRead')}
          </Button>
        ) : null
      }
    >
      {loading ? (
        <Spin />
      ) : items.length === 0 ? (
        <Empty description={t('empty')} />
      ) : (
        <List
          dataSource={items}
          renderItem={(item) => (
            <List.Item
              key={item.id}
              style={{
                cursor: item.action_url ? 'pointer' : 'default',
                background: item.is_read ? undefined : 'rgba(22,119,255,0.05)',
                padding: '12px 8px',
              }}
              onClick={() => void handleClick(item)}
              actions={
                item.is_read
                  ? [<CheckOutlined key="read" style={{ color: '#52c41a' }} />]
                  : undefined
              }
            >
              <List.Item.Meta
                title={
                  <Space size={6} wrap>
                    <Tag color={SEVERITY_COLOR[item.severity] ?? 'default'}>{item.severity}</Tag>
                    <Typography.Text strong={!item.is_read}>{renderTitle(item)}</Typography.Text>
                  </Space>
                }
                description={
                  <Space direction="vertical" size={2} style={{ width: '100%' }}>
                    {item.body && (
                      <Typography.Paragraph
                        ellipsis={{ rows: 2 }}
                        type="secondary"
                        style={{ marginBottom: 0 }}
                      >
                        {item.body}
                      </Typography.Paragraph>
                    )}
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {dayjs(item.created_at).format('YYYY-MM-DD HH:mm')}
                    </Typography.Text>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      )}
    </Drawer>
  )
}
