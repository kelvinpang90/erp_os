import { App, Card, Form, Skeleton, Space, Switch, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'

interface AISettingsResponse {
  master_enabled: boolean
  features: Record<string, boolean>
}

const FEATURE_KEYS = ['OCR_INVOICE', 'EINVOICE_PRECHECK', 'DASHBOARD_SUMMARY'] as const
type FeatureKey = (typeof FEATURE_KEYS)[number]

export default function AIFeaturesPage() {
  const { t } = useTranslation('settings')
  const { message } = App.useApp()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [settings, setSettings] = useState<AISettingsResponse | null>(null)

  useEffect(() => {
    void load()
  }, [])

  async function load() {
    setLoading(true)
    try {
      const res = await axiosInstance.get<AISettingsResponse>('/admin/ai-settings')
      // Ensure all documented feature keys exist so the toggles render predictably.
      const features = { ...res.data.features }
      for (const key of FEATURE_KEYS) features[key] ??= true
      setSettings({ master_enabled: res.data.master_enabled, features })
    } catch {
      message.error(t('ai.load_failed'))
    } finally {
      setLoading(false)
    }
  }

  async function save(next: AISettingsResponse) {
    setSaving(true)
    try {
      const res = await axiosInstance.put<AISettingsResponse>('/admin/ai-settings', next)
      const features = { ...res.data.features }
      for (const key of FEATURE_KEYS) features[key] ??= true
      setSettings({ master_enabled: res.data.master_enabled, features })
      message.success(t('ai.save_success'))
    } catch {
      message.error(t('ai.save_failed'))
    } finally {
      setSaving(false)
    }
  }

  if (loading || !settings) {
    return (
      <Card title={t('ai.title')}>
        <Skeleton active paragraph={{ rows: 4 }} />
      </Card>
    )
  }

  const onMasterChange = (checked: boolean) => {
    void save({ ...settings, master_enabled: checked })
  }

  const onFeatureChange = (key: FeatureKey, checked: boolean) => {
    void save({
      ...settings,
      features: { ...settings.features, [key]: checked },
    })
  }

  return (
    <Card title={t('ai.title')}>
      <Typography.Paragraph type="secondary">{t('ai.description')}</Typography.Paragraph>

      <Form layout="vertical" disabled={saving}>
        <Form.Item label={<strong>{t('ai.master_label')}</strong>} extra={t('ai.master_help')}>
          <Switch checked={settings.master_enabled} onChange={onMasterChange} />
        </Form.Item>

        <Typography.Title level={5} style={{ marginTop: 24 }}>
          {t('ai.per_feature_label')}
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          {t('ai.per_feature_help')}
        </Typography.Paragraph>

        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          {FEATURE_KEYS.map((key) => (
            <Form.Item key={key} label={t(`ai.features.${key}.title`)} extra={t(`ai.features.${key}.desc`)}>
              <Switch
                checked={settings.features[key] ?? true}
                onChange={(checked) => onFeatureChange(key, checked)}
                disabled={!settings.master_enabled}
              />
            </Form.Item>
          ))}
        </Space>
      </Form>
    </Card>
  )
}
