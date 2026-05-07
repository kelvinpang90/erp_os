import { ReloadOutlined, RobotOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Empty, List, Space, Spin, Tag, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import type { AISummaryEnvelope } from './types'

interface Props {
  envelope: AISummaryEnvelope
  refreshing: boolean
  canRefresh: boolean
  onRefresh: () => void
}

function formatStaleness(seconds: number, t: (k: string, opts?: Record<string, unknown>) => string) {
  if (seconds < 60) return t('summary.fresh')
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return t('summary.stale_minutes', { minutes })
  const hours = Math.floor(minutes / 60)
  return t('summary.stale_hours', { hours })
}

function stalenessColor(seconds: number, isStale: boolean): string {
  if (!isStale) return 'green'
  if (seconds < 7200) return 'gold'
  return 'red'
}

export default function AISummaryCard({ envelope, refreshing, canRefresh, onRefresh }: Props) {
  const { t, i18n } = useTranslation('dashboard')

  // The payload carries both English and Simplified Chinese versions.
  // Pick whichever matches the active i18n language so language switching
  // is instant — no extra backend round-trip.
  const content = envelope.payload
    ? i18n.language?.startsWith('zh')
      ? envelope.payload.zh
      : envelope.payload.en
    : null

  const showError =
    envelope.error_code &&
    envelope.error_code !== 'NEVER_GENERATED' &&
    envelope.error_code !== 'AI_DISABLED'

  return (
    <Card
      title={
        <Space>
          <RobotOutlined />
          <span>{t('summary.title')}</span>
          {envelope.available && envelope.payload && (
            <Tag color={stalenessColor(envelope.staleness_seconds, envelope.is_stale)}>
              {formatStaleness(envelope.staleness_seconds, t)}
            </Tag>
          )}
        </Space>
      }
      extra={
        canRefresh && envelope.available ? (
          <Button
            size="small"
            type="primary"
            icon={<ReloadOutlined spin={refreshing} />}
            onClick={onRefresh}
            loading={refreshing}
          >
            {refreshing ? t('summary.refreshing') : t('summary.refresh')}
          </Button>
        ) : null
      }
    >
      {!envelope.available && (
        <Empty description={t('summary.ai_disabled')} />
      )}

      {envelope.available && !envelope.payload && (
        <Empty description={t('summary.never_generated')}>
          {refreshing && <Spin />}
        </Empty>
      )}

      {showError && envelope.payload && (
        <Alert
          type={envelope.error_code === 'AI_TIMEOUT' ? 'warning' : 'info'}
          showIcon
          message={
            envelope.error_code === 'AI_TIMEOUT'
              ? t('summary.error_timeout')
              : t('summary.error_general')
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {content && (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Title level={5} style={{ margin: 0 }}>
            {content.headline}
          </Typography.Title>

          {content.key_findings.length > 0 && (
            <div>
              <Typography.Text strong>{t('summary.key_findings')}</Typography.Text>
              <List
                size="small"
                dataSource={content.key_findings}
                renderItem={(item) => <List.Item>{item}</List.Item>}
                bordered={false}
                split={false}
              />
            </div>
          )}

          {content.action_items.length > 0 && (
            <div>
              <Typography.Text strong>{t('summary.action_items')}</Typography.Text>
              <List
                size="small"
                dataSource={content.action_items}
                renderItem={(item) => (
                  <List.Item>
                    <Tag color="processing">→</Tag> {item}
                  </List.Item>
                )}
                bordered={false}
                split={false}
              />
            </div>
          )}
        </Space>
      )}
    </Card>
  )
}
