import { ExclamationCircleOutlined } from '@ant-design/icons'
import { Alert, App, Button, Card, Descriptions, Space, Tag, Typography } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

interface DemoResetResponse {
  status: string
  message: string
  demo_reset_log_id: number | null
}

export default function DemoResetPage() {
  const { t } = useTranslation('admin')
  const { message, modal } = App.useApp()
  const demoMode = useAuthStore((s) => s.demoMode)
  const [submitting, setSubmitting] = useState(false)
  const [lastResult, setLastResult] = useState<DemoResetResponse | null>(null)

  const handleConfirm = () => {
    modal.confirm({
      title: t('demo_reset.confirm_title'),
      icon: <ExclamationCircleOutlined />,
      content: t('demo_reset.confirm_body'),
      okText: t('demo_reset.confirm_ok'),
      okButtonProps: { danger: true },
      cancelText: t('demo_reset.confirm_cancel'),
      onOk: async () => {
        setSubmitting(true)
        try {
          const res = await axiosInstance.post<DemoResetResponse>('/admin/demo-reset')
          setLastResult(res.data)
          message.success(t('demo_reset.queued'))
        } catch (err: unknown) {
          const apiErr = err as {
            response?: { data?: { error_code?: string; message?: string } }
          }
          if (apiErr?.response?.data?.error_code === 'DEMO_MODE_REQUIRED') {
            message.error(t('demo_reset.disabled'))
          } else {
            message.error(apiErr?.response?.data?.message ?? t('demo_reset.failed'))
          }
        } finally {
          setSubmitting(false)
        }
      },
    })
  }

  return (
    <Card title={t('demo_reset.title')}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Alert
          type={demoMode ? 'info' : 'warning'}
          showIcon
          message={demoMode ? t('demo_reset.mode_on') : t('demo_reset.mode_off')}
          description={demoMode ? t('demo_reset.mode_on_desc') : t('demo_reset.mode_off_desc')}
        />

        <Typography.Paragraph>{t('demo_reset.description')}</Typography.Paragraph>

        <Button
          danger
          type="primary"
          loading={submitting}
          disabled={!demoMode}
          onClick={handleConfirm}
        >
          {t('demo_reset.button')}
        </Button>

        {lastResult && (
          <Descriptions bordered size="small" column={1} title={t('demo_reset.last_run')}>
            <Descriptions.Item label={t('demo_reset.status')}>
              <Tag color="processing">{lastResult.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('demo_reset.message')}>
              {lastResult.message}
            </Descriptions.Item>
            {lastResult.demo_reset_log_id !== null && (
              <Descriptions.Item label={t('demo_reset.log_id')}>
                {lastResult.demo_reset_log_id}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Space>
    </Card>
  )
}
