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
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../../api/client'
import {
  CN_REASON_LABEL,
  CN_STATUS_COLOR,
  CN_STATUS_LABEL,
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
      message.success('Credit Note submitted to MyInvois. UIN issued.')
      load()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message
      message.error(msg ?? 'Failed to submit credit note.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      await axiosInstance.post(`/credit-notes/${id}/cancel`)
      message.success('Credit Note cancelled. Stock has been rolled back.')
      load()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message
      message.error(msg ?? 'Failed to cancel credit note.')
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
      title: 'SKU',
      dataIndex: 'sku_code',
      width: 240,
      render: (_: unknown, row: CNLine) =>
        row.sku_code ? `${row.sku_code} — ${row.sku_name}` : '-',
    },
    { title: 'Description', dataIndex: 'description', ellipsis: true },
    { title: 'Qty', dataIndex: 'qty', width: 90, align: 'right' as const },
    {
      title: 'Unit Price',
      dataIndex: 'unit_price_excl_tax',
      width: 120,
      align: 'right' as const,
    },
    {
      title: 'Tax %',
      dataIndex: 'tax_rate_percent',
      width: 70,
      align: 'right' as const,
    },
    {
      title: 'Line Total (incl. tax)',
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
              {CN_STATUS_LABEL[cn.status] ?? cn.status}
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
                Submit to MyInvois
              </Button>
            )}
            {isCancellable && (
              <Button danger onClick={handleCancel} loading={actionLoading}>
                Cancel CN
              </Button>
            )}
            <Button onClick={load}>Refresh</Button>
          </Space>
        }
      >
        <Row gutter={24}>
          <Col span={cn.uin ? 16 : 24}>
            <ProDescriptions column={2}>
              <ProDescriptions.Item label="Original Invoice">
                <a
                  onClick={() =>
                    navigate(`/sales/einvoice/${cn.invoice_id}`)
                  }
                >
                  {cn.invoice_no || `#${cn.invoice_id}`}
                </a>
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Customer">
                {cn.customer_name || `#${cn.customer_id}`}
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Reason">
                {CN_REASON_LABEL[cn.reason] ?? cn.reason}
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Business Date">
                {cn.business_date}
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Currency">
                {cn.currency} (rate{' '}
                {parseFloat(cn.exchange_rate).toFixed(4)})
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Submitted At">
                {cn.submitted_at
                  ? new Date(cn.submitted_at).toLocaleString('en-MY')
                  : '—'}
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Validated At">
                {cn.validated_at
                  ? new Date(cn.validated_at).toLocaleString('en-MY')
                  : '—'}
              </ProDescriptions.Item>
              {cn.reason_description && (
                <ProDescriptions.Item label="Detail" span={2}>
                  {cn.reason_description}
                </ProDescriptions.Item>
              )}
              {cn.remarks && (
                <ProDescriptions.Item label="Remarks" span={2}>
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
                  QR code (mock URL)
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
          message="DRAFT — not yet sent to LHDN"
          description="Click 'Submit to MyInvois' to obtain a UIN. Cancelling at this point will roll back stock automatically."
        />
      )}

      <Card title="Credit Note Lines">
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
              Subtotal (excl. tax):
            </Typography.Text>{' '}
            <Typography.Text>{fmt(cn.subtotal_excl_tax)}</Typography.Text>
          </Col>
          <Col>
            <Typography.Text type="secondary">Tax:</Typography.Text>{' '}
            <Typography.Text>{fmt(cn.tax_amount)}</Typography.Text>
          </Col>
          <Col>
            <Typography.Text strong>Total Credit (incl. tax):</Typography.Text>{' '}
            <Typography.Text strong>{fmt(cn.total_incl_tax)}</Typography.Text>
          </Col>
        </Row>
      </Card>
    </Space>
  )
}
