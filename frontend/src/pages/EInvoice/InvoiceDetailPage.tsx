import { ArrowLeftOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Modal,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import CountdownTimer from './CountdownTimer'
import { STATUS_COLOR, STATUS_LABEL } from './InvoiceColumns'
import PrecheckModal from './PrecheckModal'

interface InvoiceLine {
  id: number
  line_no: number
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
  discount_amount: string
  line_total_excl_tax: string
  line_total_incl_tax: string
  msic_code?: string | null
}

interface InvoiceDetail {
  id: number
  document_no: string
  invoice_type: string
  status: string
  sales_order_id?: number
  sales_order_no?: string
  customer_id: number
  customer_name?: string
  warehouse_id?: number
  warehouse_name?: string
  business_date: string
  due_date?: string
  currency: string
  exchange_rate: string
  subtotal_excl_tax: string
  tax_amount: string
  discount_amount: string
  total_incl_tax: string
  base_currency_amount: string
  paid_amount: string
  uin?: string | null
  qr_code_url?: string | null
  submitted_at?: string | null
  validated_at?: string | null
  finalized_at?: string | null
  rejected_at?: string | null
  rejected_by?: string | null
  rejection_reason?: string | null
  remarks?: string | null
  finalize_window_seconds: number
  seconds_until_finalize?: number | null
  lines: InvoiceLine[]
}

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [inv, setInv] = useState<InvoiceDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [rejectModal, setRejectModal] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [precheckOpen, setPrecheckOpen] = useState(false)

  const loadInvoice = () => {
    if (!id) return
    setLoading(true)
    axiosInstance
      .get(`/invoices/${id}`)
      .then((res) => setInv(res.data))
      .catch(() => navigate('/sales/einvoice'))
      .finally(() => setLoading(false))
  }

  useEffect(loadInvoice, [id])

  const handleReject = async () => {
    if (!id || rejectReason.trim().length < 3) {
      message.warning('Rejection reason must be at least 3 characters.')
      return
    }
    setActionLoading(true)
    try {
      await axiosInstance.post(`/invoices/${id}/reject`, { reason: rejectReason })
      message.success('Invoice rejected by buyer.')
      setRejectModal(false)
      setRejectReason('')
      loadInvoice()
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { message?: string; detail?: { errors?: { msg?: string; loc?: (string | number)[] }[] } } } })
        ?.response?.data
      // Surface Pydantic field-level errors when available (the generic
      // "Request validation failed" alone is unhelpful).
      const fieldErrors = data?.detail?.errors
        ?.map((e) => `${(e.loc ?? []).filter((p) => p !== 'body').join('.')}: ${e.msg ?? ''}`)
        .filter(Boolean)
        .join('; ')
      message.error(fieldErrors || data?.message || 'Failed to reject invoice.')
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
  if (!inv) return null

  const fmt = (val: string) =>
    `${inv.currency} ${parseFloat(val).toLocaleString('en-MY', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`

  const lineColumns = [
    { title: '#', dataIndex: 'line_no', width: 50 },
    {
      title: 'SKU',
      dataIndex: 'sku_code',
      width: 240,
      render: (_: unknown, row: InvoiceLine) =>
        row.sku_code ? `${row.sku_code} — ${row.sku_name}` : '-',
    },
    { title: 'Description', dataIndex: 'description', ellipsis: true },
    { title: 'MSIC', dataIndex: 'msic_code', width: 90, render: (v: string | null) => v ?? '—' },
    { title: 'Qty', dataIndex: 'qty', width: 90, align: 'right' as const },
    { title: 'Unit Price', dataIndex: 'unit_price_excl_tax', width: 120, align: 'right' as const },
    { title: 'Tax %', dataIndex: 'tax_rate_percent', width: 70, align: 'right' as const },
    {
      title: 'Line Total (incl. tax)',
      dataIndex: 'line_total_incl_tax',
      width: 160,
      align: 'right' as const,
      render: (val: string) =>
        parseFloat(val).toLocaleString('en-MY', { minimumFractionDigits: 2 }),
    },
  ]

  const isSubmittable = inv.status === 'DRAFT'
  const isRejectable =
    inv.status === 'VALIDATED' &&
    inv.seconds_until_finalize !== null &&
    inv.seconds_until_finalize !== undefined &&
    inv.seconds_until_finalize > 0
  const isValidated = inv.status === 'VALIDATED'
  // Window 12: Credit Note can be issued against any non-cancelled invoice
  // that LHDN has accepted (VALIDATED or FINAL).
  const isCreditable = inv.status === 'VALIDATED' || inv.status === 'FINAL'

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              type="text"
              onClick={() => navigate('/sales/einvoice')}
            />
            <Typography.Text strong>{inv.document_no}</Typography.Text>
            <Tag color={STATUS_COLOR[inv.status] ?? 'default'}>
              {STATUS_LABEL[inv.status] ?? inv.status}
            </Tag>
            {inv.uin && <Tag color="purple">UIN: {inv.uin}</Tag>}
          </Space>
        }
        extra={
          <Space>
            {isSubmittable && (
              <Button
                type="primary"
                loading={actionLoading}
                onClick={() => setPrecheckOpen(true)}
              >
                Run Precheck &amp; Submit
              </Button>
            )}
            {isCreditable && (
              <Button
                onClick={() =>
                  navigate(`/sales/credit-notes/new?invoice_id=${inv.id}`)
                }
              >
                Issue Credit Note
              </Button>
            )}
            {isRejectable && (
              <Button danger onClick={() => setRejectModal(true)}>
                Reject as Buyer
              </Button>
            )}
            <Button onClick={loadInvoice}>Refresh</Button>
          </Space>
        }
      >
        <Row gutter={24}>
          <Col span={isValidated ? 16 : 24}>
            <ProDescriptions column={2}>
              <ProDescriptions.Item label="Sales Order">
                {inv.sales_order_no ? (
                  <a onClick={() => navigate(`/sales/orders/${inv.sales_order_id}`)}>
                    {inv.sales_order_no}
                  </a>
                ) : (
                  '—'
                )}
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Customer">
                {inv.customer_name || `#${inv.customer_id}`}
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Warehouse">
                {inv.warehouse_name || (inv.warehouse_id ? `#${inv.warehouse_id}` : '—')}
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Type">{inv.invoice_type}</ProDescriptions.Item>
              <ProDescriptions.Item label="Business Date">
                {inv.business_date}
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Due Date">{inv.due_date ?? '—'}</ProDescriptions.Item>
              <ProDescriptions.Item label="Currency">
                {inv.currency} (rate {parseFloat(inv.exchange_rate).toFixed(4)})
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Submitted At">
                {inv.submitted_at
                  ? new Date(inv.submitted_at).toLocaleString('en-MY')
                  : '—'}
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Validated At">
                {inv.validated_at
                  ? new Date(inv.validated_at).toLocaleString('en-MY')
                  : '—'}
              </ProDescriptions.Item>
              <ProDescriptions.Item label="Finalized At">
                {inv.finalized_at
                  ? new Date(inv.finalized_at).toLocaleString('en-MY')
                  : '—'}
              </ProDescriptions.Item>
              {inv.rejected_at && (
                <ProDescriptions.Item label="Rejected" span={2}>
                  <Typography.Text type="danger">
                    {new Date(inv.rejected_at).toLocaleString('en-MY')} by{' '}
                    {inv.rejected_by ?? '—'}: {inv.rejection_reason}
                  </Typography.Text>
                </ProDescriptions.Item>
              )}
              {inv.remarks && (
                <ProDescriptions.Item label="Remarks" span={2}>
                  {inv.remarks}
                </ProDescriptions.Item>
              )}
            </ProDescriptions>
          </Col>
          {isValidated && (
            <Col span={8}>
              <Card size="small" style={{ textAlign: 'center', background: '#fafafa' }}>
                {inv.qr_code_url && (
                  <div style={{ marginBottom: 12 }}>
                    <img
                      src={inv.qr_code_url}
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
                  </div>
                )}
                <CountdownTimer
                  initialSeconds={inv.seconds_until_finalize ?? 0}
                  windowSeconds={inv.finalize_window_seconds}
                  onElapsed={loadInvoice}
                />
              </Card>
            </Col>
          )}
        </Row>
      </Card>

      {inv.status === 'DRAFT' && (
        <Alert
          type="info"
          showIcon
          message="DRAFT — not yet sent to LHDN"
          description="Click 'Submit to MyInvois' to obtain a UIN. The mock adapter responds synchronously and the invoice will move to VALIDATED."
        />
      )}
      {inv.status === 'FINAL' && (
        <Alert
          type="success"
          showIcon
          message="FINAL — opposition window has closed"
          description="This invoice is now a legal tax document. Modifications must go through a Credit Note (Window 12)."
        />
      )}

      <Card title="Invoice Lines">
        <Row gutter={16}>
          <Col span={24}>
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
                {inv.lines.map((ln) => (
                  <tr key={ln.id} style={{ borderBottom: '1px solid #f5f5f5' }}>
                    {lineColumns.map((c) => {
                      const k = c.dataIndex as keyof InvoiceLine
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
          </Col>
        </Row>
        <Row gutter={16} justify="end" style={{ marginTop: 16 }}>
          <Col>
            <Typography.Text type="secondary">Subtotal (excl. tax):</Typography.Text>{' '}
            <Typography.Text>{fmt(inv.subtotal_excl_tax)}</Typography.Text>
          </Col>
          <Col>
            <Typography.Text type="secondary">Tax:</Typography.Text>{' '}
            <Typography.Text>{fmt(inv.tax_amount)}</Typography.Text>
          </Col>
          <Col>
            <Typography.Text strong>Total (incl. tax):</Typography.Text>{' '}
            <Typography.Text strong>{fmt(inv.total_incl_tax)}</Typography.Text>
          </Col>
        </Row>
      </Card>

      <PrecheckModal
        open={precheckOpen}
        invoiceId={inv.id}
        onClose={() => setPrecheckOpen(false)}
        onSubmitted={loadInvoice}
      />

      <Modal
        title="Reject Invoice (as Buyer)"
        open={rejectModal}
        onOk={handleReject}
        onCancel={() => {
          setRejectModal(false)
          setRejectReason('')
        }}
        confirmLoading={actionLoading}
        okButtonProps={{ danger: true }}
        okText="Reject"
      >
        <Typography.Paragraph>
          Reject this invoice on behalf of the buyer. Allowed only inside the 72h
          opposition window (72s in DEMO_MODE). Reason will be sent to LHDN
          (minimum 3 characters).
        </Typography.Paragraph>
        <Input.TextArea
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          rows={3}
          placeholder="e.g. Wrong amount on line 2"
          maxLength={1000}
          showCount
        />
      </Modal>
    </Space>
  )
}
