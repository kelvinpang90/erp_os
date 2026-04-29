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

const SEVERITY_TAG: Record<string, { color: string; label: string }> = {
  INFO: { color: 'blue', label: 'INFO' },
  WARN: { color: 'orange', label: 'WARN' },
  ERROR: { color: 'red', label: 'ERROR' },
}

const ITEM_LABELS: Record<string, string> = {
  // Hard
  SELLER_TIN_FORMAT: 'Seller TIN format',
  BUYER_TIN_PRESENT_OR_B2C: 'Buyer TIN required (B2B) / optional (B2C)',
  MSIC_CODE_PRESENT: 'MSIC code on header + every line',
  SST_TAX_AMOUNT_CONSISTENT: 'SST tax math consistent',
  SST_RATE_VALID: 'Valid SST rates (0% / 6% / 10%)',
  LINE_TOTAL_CONSISTENT: 'Line subtotal sums to header',
  CURRENCY_RATE_PRESENT: 'Foreign-currency exchange rate set',
  // Soft (LLM)
  BUYER_NAME_VS_TYPE_LOOKS_CONSISTENT: 'Buyer name pattern matches B2B/B2C',
  LINE_DESCRIPTION_QUALITY: 'Line descriptions are specific',
  BUSINESS_DATE_REASONABLE: 'Business date is reasonable',
}

function statusBanner(status: string): { type: 'success' | 'warning' | 'error'; title: string; desc: string } {
  if (status === 'PASS') {
    return {
      type: 'success',
      title: 'Ready to Submit',
      desc: 'All checks passed. Click Submit to send this invoice to MyInvois.',
    }
  }
  if (status === 'WARN') {
    return {
      type: 'warning',
      title: 'Warnings — review before submitting',
      desc:
        'Some soft checks raised warnings. You can still submit, but consider fixing the flagged items first.',
    }
  }
  return {
    type: 'error',
    title: 'Hard rule failures detected',
    desc:
      'One or more hard rules failed. Submitting now is likely to be rejected by LHDN. Acknowledge the risk to force-submit.',
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
          'Precheck failed.'
        setError(msg)
      })
      .finally(() => setLoading(false))
  }, [open, invoiceId])

  const handleSubmit = async () => {
    if (!invoiceId) return
    setSubmitting(true)
    try {
      await axiosInstance.post(`/invoices/${invoiceId}/submit`)
      message.success('Invoice submitted to MyInvois. UIN issued.')
      onSubmitted()
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? 'Failed to submit invoice.')
    } finally {
      setSubmitting(false)
    }
  }

  const overall = result?.overall_status ?? 'PASS'
  const banner = statusBanner(overall)
  const submitDisabled =
    submitting || !result || (overall === 'FAIL' && !acknowledged)
  const submitLabel =
    overall === 'PASS'
      ? 'Submit to MyInvois'
      : overall === 'WARN'
        ? 'Continue Submit'
        : 'Force Submit'
  const submitDanger = overall === 'FAIL'

  return (
    <Modal
      title="e-Invoice Precheck"
      open={open}
      onCancel={onClose}
      width={720}
      destroyOnHidden
      footer={
        <Space>
          <Button onClick={onClose} disabled={submitting}>
            Cancel
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
            Running compliance checklist…
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
              message="AI check unavailable — only hard rules applied"
              description={
                result.ai_error
                  ? `Reason: ${result.ai_error}. The 3 soft semantic checks were skipped.`
                  : 'The 3 soft semantic checks were skipped.'
              }
            />
          )}

          <List
            size="small"
            dataSource={result.items}
            renderItem={(item) => {
              const label = ITEM_LABELS[item.code] ?? item.code
              const sev = SEVERITY_TAG[item.severity] ?? { color: 'default', label: item.severity }
              return (
                <List.Item key={item.code}>
                  <Space align="start" style={{ width: '100%' }}>
                    <span style={{ marginTop: 2 }}>{passedIcon(item)}</span>
                    <div style={{ flex: 1 }}>
                      <Space>
                        <Typography.Text strong>{label}</Typography.Text>
                        <Tag color={item.category === 'hard' ? 'geekblue' : 'purple'}>
                          {item.category}
                        </Tag>
                        {!item.passed && <Tag color={sev.color}>{sev.label}</Tag>}
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
              I acknowledge the risks above and want to force-submit anyway.
            </Checkbox>
          )}
        </Space>
      )}
    </Modal>
  )
}
