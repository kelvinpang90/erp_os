import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Checkbox,
  List,
  Modal,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'

interface PrecheckItem {
  code: string
  category: 'hard' | 'soft'
  severity: 'INFO' | 'WARN' | 'ERROR'
  passed: boolean
  message: string
  suggestion?: string | null
}

interface PrecheckResult {
  version: string
  checked_at: string
  overall_status: 'PASS' | 'WARN' | 'FAIL'
  ai_used: boolean
  ai_error?: string | null
  items: PrecheckItem[]
}

interface Props {
  open: boolean
  invoiceId: number | null
  onClose: () => void
  /** Called after a successful submit; parent should reload the invoice. */
  onSubmitted: () => void
}

const SEVERITY_COLOR: Record<string, string> = {
  INFO: 'blue',
  WARN: 'orange',
  ERROR: 'red',
}

type Translator = (key: string, opts?: Record<string, unknown>) => string

function statusBanner(t: Translator, status: string): { type: 'success' | 'warning' | 'error'; title: string; desc: string } {
  if (status === 'PASS') {
    return {
      type: 'success',
      title: t('precheck.banner.passTitle'),
      desc: t('precheck.banner.passDesc'),
    }
  }
  if (status === 'WARN') {
    return {
      type: 'warning',
      title: t('precheck.banner.warnTitle'),
      desc: t('precheck.banner.warnDesc'),
    }
  }
  return {
    type: 'error',
    title: t('precheck.banner.failTitle'),
    desc: t('precheck.banner.failDesc'),
  }
}

function passedIcon(item: PrecheckItem) {
  if (item.passed) {
    return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />
  }
  if (item.severity === 'ERROR') {
    return <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 18 }} />
  }
  if (item.severity === 'WARN') {
    return <ExclamationCircleOutlined style={{ color: '#faad14', fontSize: 18 }} />
  }
  return <InfoCircleOutlined style={{ color: '#1677ff', fontSize: 18 }} />
}

export default function PrecheckModal({ open, invoiceId, onClose, onSubmitted }: Props) {
  const { t } = useTranslation('einvoice')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<PrecheckResult | null>(null)
  const [acknowledged, setAcknowledged] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Trigger precheck whenever the Modal opens with a fresh invoice id.
  useEffect(() => {
    if (!open || !invoiceId) return
    setLoading(true)
    setError(null)
    setResult(null)
    setAcknowledged(false)
    axiosInstance
      .post(`/invoices/${invoiceId}/precheck`)
      .then((res) => setResult(res.data?.precheck_result ?? null))
      .catch((err: unknown) => {
        const msg =
          (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
          t('precheck.failed')
        setError(msg)
      })
      .finally(() => setLoading(false))
  }, [open, invoiceId])

  const handleSubmit = async () => {
    if (!invoiceId) return
    setSubmitting(true)
    try {
      await axiosInstance.post(`/invoices/${invoiceId}/submit`)
      message.success(t('messages.submitted'))
      onSubmitted()
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? t('messages.submitFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const overall = result?.overall_status ?? 'PASS'
  const banner = statusBanner(t, overall)
  const submitDisabled =
    submitting || !result || (overall === 'FAIL' && !acknowledged)
  const submitLabel =
    overall === 'PASS'
      ? t('submit_to_myinvois')
      : overall === 'WARN'
        ? t('precheck.buttons.continueSubmit')
        : t('precheck.buttons.forceSubmit')
  const submitDanger = overall === 'FAIL'

  return (
    <Modal
      title={t('precheck.modalTitle')}
      open={open}
      onCancel={onClose}
      width={720}
      destroyOnHidden
      footer={
        <Space>
          <Button onClick={onClose} disabled={submitting}>
            {t('precheck.buttons.cancel')}
          </Button>
          <Button
            type="primary"
            danger={submitDanger}
            loading={submitting}
            disabled={submitDisabled}
            onClick={handleSubmit}
          >
            {submitLabel}
          </Button>
        </Space>
      }
    >
      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
          <div style={{ marginTop: 12, color: '#888' }}>
            {t('precheck.running')}
          </div>
        </div>
      )}

      {error && !loading && <Alert type="error" message={error} showIcon />}

      {!loading && result && (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            type={banner.type}
            message={banner.title}
            description={banner.desc}
            showIcon
          />

          {!result.ai_used && (
            <Alert
              type="info"
              showIcon
              message={t('precheck.aiUnavailable')}
              description={
                result.ai_error
                  ? t('precheck.aiUnavailableReason', { reason: result.ai_error })
                  : t('precheck.aiUnavailableDefault')
              }
            />
          )}

          <List
            size="small"
            dataSource={result.items}
            renderItem={(item) => {
              const label = t(`precheck.items.${item.code}`, { defaultValue: item.code })
              const sevColor = SEVERITY_COLOR[item.severity] ?? 'default'
              const sevLabel = t(`precheck.severity.${item.severity}`, { defaultValue: item.severity })
              return (
                <List.Item key={item.code}>
                  <Space align="start" style={{ width: '100%' }}>
                    <span style={{ marginTop: 2 }}>{passedIcon(item)}</span>
                    <div style={{ flex: 1 }}>
                      <Space>
                        <Typography.Text strong>{label}</Typography.Text>
                        <Tag color={item.category === 'hard' ? 'geekblue' : 'purple'}>
                          {t(`precheck.category.${item.category}`, { defaultValue: item.category })}
                        </Tag>
                        {!item.passed && <Tag color={sevColor}>{sevLabel}</Tag>}
                      </Space>
                      <div style={{ color: item.passed ? '#888' : '#333', marginTop: 4 }}>
                        {item.message}
                      </div>
                      {!item.passed && item.suggestion && (
                        <div style={{ color: '#1677ff', marginTop: 4, fontSize: 12 }}>
                          → {item.suggestion}
                        </div>
                      )}
                    </div>
                  </Space>
                </List.Item>
              )
            }}
          />

          {overall === 'FAIL' && (
            <Checkbox
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
            >
              {t('precheck.acknowledge')}
            </Checkbox>
          )}
        </Space>
      )}
    </Modal>
  )
}
