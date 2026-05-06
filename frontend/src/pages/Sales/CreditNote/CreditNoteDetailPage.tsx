import { ArrowLeftOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import {
  Alert,
  Button,
  Card,
  Col,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../../api/client'
import {
  CN_STATUS_COLOR,
  cnReasonLabel,
  cnStatusLabel,
} from './CreditNoteColumns'

interface CNLine {
  id: number
  line_no: number
  invoice_line_id: number
  sku_id: number
  sku_code?: string
  sku_name?: string
  description: string
  uom_id: number
  uom_code?: string
  qty: string
  unit_price_excl_tax: string
  tax_rate_percent: string
  tax_amount: string
  line_total_excl_tax: string
  line_total_incl_tax: string
  snapshot_avg_cost?: string | null
}

interface CreditNoteDetail {
  id: number
  document_no: string
  status: string
  invoice_id: number
  invoice_no?: string
  customer_id: number
  customer_name?: string
  business_date: string
  reason: string
  reason_description?: string | null
  currency: string
  exchange_rate: string
  subtotal_excl_tax: string
  tax_amount: string
  total_incl_tax: string
  base_currency_amount: string
  seller_tin?: string | null
  buyer_tin?: string | null
  uin?: string | null
  qr_code_url?: string | null
  submitted_at?: string | null
  validated_at?: string | null
  rejection_reason?: string | null
  remarks?: string | null
  lines: CNLine[]
}

export default function CreditNoteDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation(['einvoice', 'common'])
  const tEinvoice = (key: string, opts?: Record<string, unknown>) =>
    t(`einvoice:${key}`, (opts ?? {}) as never) as unknown as string
  const [cn, setCn] = useState<CreditNoteDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  const load = () => {
    if (!id) return
    setLoading(true)
    axiosInstance
      .get(`/credit-notes/${id}`)
      .then((res) => setCn(res.data))
      .catch(() => navigate('/sales/credit-notes'))
      .finally(() => setLoading(false))
  }
  useEffect(load, [id])

  const handleSubmit = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      await axiosInstance.post(`/credit-notes/${id}/submit`)
      message.success(t('einvoice:creditNote.messages.submitted'))
      load()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message
      message.error(msg ?? t('einvoice:creditNote.messages.submitFailed'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      await axiosInstance.post(`/credit-notes/${id}/cancel`)
      message.success(t('einvoice:creditNote.messages.cancelled'))
      load()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message
      message.error(msg ?? t('einvoice:creditNote.messages.cancelFailed'))
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <Spin
        size="large"
        style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }}
      />
    )
  }
  if (!cn) return null

  const fmt = (val: string) =>
    `${cn.currency} ${parseFloat(val).toLocaleString('en-MY', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`

  const isSubmittable = cn.status === 'DRAFT'
  const isCancellable = cn.status === 'DRAFT'

  const lineColumns = [
    { title: '#', dataIndex: 'line_no', width: 50 },
    {
      title: t('einvoice:sku'),
      dataIndex: 'sku_code',
      width: 240,
      render: (_: unknown, row: CNLine) =>
        row.sku_code ? `${row.sku_code} — ${row.sku_name}` : '-',
    },
    { title: t('einvoice:description'), dataIndex: 'description', ellipsis: true },
    { title: t('einvoice:qty'), dataIndex: 'qty', width: 90, align: 'right' as const },
    {
      title: t('einvoice:columns.unitPrice'),
      dataIndex: 'unit_price_excl_tax',
      width: 120,
      align: 'right' as const,
    },
    {
      title: t('einvoice:columns.taxPct'),
      dataIndex: 'tax_rate_percent',
      width: 70,
      align: 'right' as const,
    },
    {
      title: t('einvoice:line_total_incl_tax'),
      dataIndex: 'line_total_incl_tax',
      width: 160,
      align: 'right' as const,
      render: (val: string) =>
        parseFloat(val).toLocaleString('en-MY', {
          minimumFractionDigits: 2,
        }),
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              type="text"
              onClick={() => navigate('/sales/credit-notes')}
            />
            <Typography.Text strong>{cn.document_no}</Typography.Text>
            <Tag color={CN_STATUS_COLOR[cn.status] ?? 'default'}>
              {cnStatusLabel(tEinvoice, cn.status)}
            </Tag>
            {cn.uin && <Tag color="purple">UIN: {cn.uin}</Tag>}
          </Space>
        }
        extra={
          <Space>
            {isSubmittable && (
              <Button
                type="primary"
                loading={actionLoading}
                onClick={handleSubmit}
              >
                {t('einvoice:submit_to_myinvois')}
              </Button>
            )}
            {isCancellable && (
              <Button danger onClick={handleCancel} loading={actionLoading}>
                {t('einvoice:creditNote.buttons.cancel')}
              </Button>
            )}
            <Button onClick={load}>{t('einvoice:refresh')}</Button>
          </Space>
        }
      >
        <Row gutter={24}>
          <Col span={cn.uin ? 16 : 24}>
            <ProDescriptions column={2}>
              <ProDescriptions.Item label={t('einvoice:creditNote.fields.originalInvoice')}>
                <a
                  onClick={() =>
                    navigate(`/sales/einvoice/${cn.invoice_id}`)
                  }
                >
                  {cn.invoice_no || `#${cn.invoice_id}`}
                </a>
              </ProDescriptions.Item>
              <ProDescriptions.Item label={t('einvoice:customer')}>
                {cn.customer_name || `#${cn.customer_id}`}
              </ProDescriptions.Item>
              <ProDescriptions.Item label={t('einvoice:seller_tin')}>
                {cn.seller_tin || <span style={{ color: '#ff4d4f' }}>{t('einvoice:tin_missing')}</span>}
              </ProDescriptions.Item>
              <ProDescriptions.Item label={t('einvoice:buyer_tin')}>
                {cn.buyer_tin || <span style={{ color: '#ff4d4f' }}>{t('einvoice:tin_missing')}</span>}
              </ProDescriptions.Item>
              <ProDescriptions.Item label={t('einvoice:creditNote.fields.reason')}>
                {cnReasonLabel(tEinvoice, cn.reason)}
              </ProDescriptions.Item>
              <ProDescriptions.Item label={t('einvoice:business_date')}>
                {cn.business_date}
              </ProDescriptions.Item>
              <ProDescriptions.Item label={t('einvoice:currency')}>
                {cn.currency} (rate{' '}
                {parseFloat(cn.exchange_rate).toFixed(4)})
              </ProDescriptions.Item>
              <ProDescriptions.Item label={t('einvoice:submitted_at')}>
                {cn.submitted_at
                  ? new Date(cn.submitted_at).toLocaleString('en-MY')
                  : '—'}
              </ProDescriptions.Item>
              <ProDescriptions.Item label={t('einvoice:validated_at')}>
                {cn.validated_at
                  ? new Date(cn.validated_at).toLocaleString('en-MY')
                  : '—'}
              </ProDescriptions.Item>
              {cn.reason_description && (
                <ProDescriptions.Item label={t('einvoice:creditNote.fields.detail')} span={2}>
                  {cn.reason_description}
                </ProDescriptions.Item>
              )}
              {cn.remarks && (
                <ProDescriptions.Item label={t('einvoice:remarks')} span={2}>
                  {cn.remarks}
                </ProDescriptions.Item>
              )}
            </ProDescriptions>
          </Col>
          {cn.qr_code_url && (
            <Col span={8}>
              <Card
                size="small"
                style={{ textAlign: 'center', background: '#fafafa' }}
              >
                <img
                  src={cn.qr_code_url}
                  alt="QR"
                  style={{
                    width: 120,
                    height: 120,
                    background: '#fff',
                    border: '1px solid #eee',
                    borderRadius: 4,
                    objectFit: 'contain',
                  }}
                  onError={(e) => {
                    ;(e.target as HTMLImageElement).style.display = 'none'
                  }}
                />
                <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                  {t('einvoice:qrCodeMock')}
                </div>
              </Card>
            </Col>
          )}
        </Row>
      </Card>

      {cn.status === 'DRAFT' && (
        <Alert
          type="info"
          showIcon
          message={t('einvoice:draft_hint')}
          description={t('einvoice:creditNote.draftHintDesc')}
        />
      )}

      <Card title={t('einvoice:creditNote.linesTitle')}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #eee', background: '#fafafa' }}>
              {lineColumns.map((c) => (
                <th
                  key={c.dataIndex as string}
                  style={{
                    padding: 8,
                    textAlign: c.align ?? 'left',
                    width: c.width,
                    fontWeight: 600,
                  }}
                >
                  {c.title as string}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cn.lines.map((ln) => (
              <tr key={ln.id} style={{ borderBottom: '1px solid #f5f5f5' }}>
                {lineColumns.map((c) => {
                  const k = c.dataIndex as keyof CNLine
                  const v = ln[k] as string | number | null
                  const display = c.render
                    ? c.render(v as never, ln as never)
                    : v == null
                      ? '—'
                      : String(v)
                  return (
                    <td
                      key={c.dataIndex as string}
                      style={{ padding: 8, textAlign: c.align ?? 'left' }}
                    >
                      {display as React.ReactNode}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>

        <Row gutter={16} justify="end" style={{ marginTop: 16 }}>
          <Col>
            <Typography.Text type="secondary">
              {t('einvoice:subtotal_excl_tax')}:
            </Typography.Text>{' '}
            <Typography.Text>{fmt(cn.subtotal_excl_tax)}</Typography.Text>
          </Col>
          <Col>
            <Typography.Text type="secondary">{t('einvoice:tax_amount')}:</Typography.Text>{' '}
            <Typography.Text>{fmt(cn.tax_amount)}</Typography.Text>
          </Col>
          <Col>
            <Typography.Text strong>{t('einvoice:creditNote.totalCredit')}:</Typography.Text>{' '}
            <Typography.Text strong>{fmt(cn.total_incl_tax)}</Typography.Text>
          </Col>
        </Row>
      </Card>
    </Space>
  )
}
