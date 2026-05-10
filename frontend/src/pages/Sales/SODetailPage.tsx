import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import { Button, Card, Col, Modal, Row, Space, Spin, Table, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface SOLine {
  id: number
  line_no: number
  sku_id: number
  sku_code?: string
  sku_name?: string
  uom_id: number
  description?: string
  qty_ordered: string
  qty_shipped: string
  qty_invoiced: string
  unit_price_excl_tax: string
  tax_rate_percent: string
  discount_percent: string
  line_total_excl_tax: string
  line_total_incl_tax: string
  snapshot_avg_cost?: string | null
}

interface SODetail {
  id: number
  document_no: string
  status: string
  customer_id: number
  customer_name: string
  warehouse_id: number
  warehouse_name: string
  business_date: string
  expected_ship_date?: string
  currency: string
  exchange_rate: string
  subtotal_excl_tax: string
  tax_amount: string
  discount_amount: string
  shipping_amount: string
  total_incl_tax: string
  payment_terms_days: number
  shipping_address?: string
  remarks?: string
  cancel_reason?: string
  confirmed_at?: string
  fully_shipped_at?: string
  cancelled_at?: string
  created_at: string
  lines: SOLine[]
}

const STATUS_COLOR: Record<string, string> = {
  DRAFT: 'default',
  CONFIRMED: 'blue',
  PARTIAL_SHIPPED: 'gold',
  FULLY_SHIPPED: 'cyan',
  INVOICED: 'purple',
  PAID: 'green',
  CANCELLED: 'red',
}

export default function SODetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation(['sales_order', 'einvoice', 'common'])
  const [so, setSO] = useState<SODetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [cancelModal, setCancelModal] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  const [invoiceId, setInvoiceId] = useState<number | null>(null)

  const loadSO = () => {
    if (!id) return
    setLoading(true)
    axiosInstance
      .get(`/sales-orders/${id}`)
      .then((res) => setSO(res.data))
      .catch(() => navigate('/sales/orders'))
      .finally(() => setLoading(false))
  }

  // Detect whether an invoice already exists for this SO so the button
  // can either jump to it or trigger generation. Window 11 enforces 1 SO ↔ 1 Invoice.
  const loadInvoiceForSO = () => {
    if (!id) return
    axiosInstance
      .get(`/invoices?sales_order_id=${id}&page_size=1`)
      .then((res) => {
        const items = res.data?.items ?? []
        setInvoiceId(items.length > 0 ? items[0].id : null)
      })
      .catch(() => setInvoiceId(null))
  }

  useEffect(() => {
    loadSO()
    loadInvoiceForSO()
  }, [id])

  const handleConfirm = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      await axiosInstance.post(`/sales-orders/${id}/confirm`)
      message.success(t('messages.confirmed'))
      loadSO()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? t('messages.confirmFailed'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleGenerateInvoice = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      const res = await axiosInstance.post(`/invoices/generate-from-so/${id}`, {})
      const newId = res.data?.id
      message.success(t('messages.invoiceGenerated', { docNo: res.data?.document_no }))
      if (newId) navigate(`/sales/einvoice/${newId}`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? t('messages.invoiceGenerateFailed'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!id || !cancelReason.trim()) {
      message.warning(t('messages.cancelReasonRequired'))
      return
    }
    setActionLoading(true)
    try {
      await axiosInstance.post(`/sales-orders/${id}/cancel`, { cancel_reason: cancelReason })
      message.success(t('messages.cancelled'))
      setCancelModal(false)
      setCancelReason('')
      loadSO()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? t('messages.cancelFailed'))
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
  if (!so) return null

  const fmt = (val: string) =>
    `${so.currency} ${parseFloat(val).toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  const lineColumns = [
    { title: '#', dataIndex: 'line_no', width: 50 },
    {
      title: t('sku'),
      dataIndex: 'sku_code',
      width: 260,
      render: (_: unknown, record: SOLine) =>
        record.sku_code ? `${record.sku_code} — ${record.sku_name}` : '-',
    },
    { title: t('description'), dataIndex: 'description', ellipsis: true },
    { title: t('qty_ordered'), dataIndex: 'qty_ordered', width: 110, align: 'right' as const },
    { title: t('qty_shipped'), dataIndex: 'qty_shipped', width: 110, align: 'right' as const },
    { title: t('columns.unitPrice'), dataIndex: 'unit_price_excl_tax', width: 120, align: 'right' as const },
    { title: t('columns.taxPct'), dataIndex: 'tax_rate_percent', width: 70, align: 'right' as const },
    { title: t('discount_percent'), dataIndex: 'discount_percent', width: 70, align: 'right' as const },
    {
      title: t('line_total_incl_tax'),
      dataIndex: 'line_total_incl_tax',
      width: 160,
      align: 'right' as const,
      render: (val: string) =>
        parseFloat(val).toLocaleString('en-MY', { minimumFractionDigits: 2 }),
    },
  ]

  // Show "Create Delivery Order" button when SO has shippable lines.
  const isShippable = so.status === 'CONFIRMED' || so.status === 'PARTIAL_SHIPPED'
  const isCancellable = so.status === 'DRAFT' || so.status === 'CONFIRMED'
  const isInvoiceable = so.status === 'PARTIAL_SHIPPED' || so.status === 'FULLY_SHIPPED'

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/sales/orders')} />
            <Typography.Text strong>{so.document_no}</Typography.Text>
            <Tag data-testid="so-status" color={STATUS_COLOR[so.status] ?? 'default'}>
              {so.status.replace(/_/g, ' ')}
            </Tag>
          </Space>
        }
        extra={
          <Space>
            {so.status === 'DRAFT' && (
              <>
                <Button onClick={() => navigate(`/sales/orders/${id}/edit`)} icon={<EditOutlined />}>
                  {t('common:edit')}
                </Button>
                <Button type="primary" loading={actionLoading} onClick={handleConfirm}>
                  {t('confirm')}
                </Button>
              </>
            )}
            {isShippable && (
              <Button
                type="primary"
                onClick={() => navigate(`/sales/delivery/create?so_id=${id}`)}
              >
                {t('create_delivery')}
              </Button>
            )}
            {isInvoiceable && invoiceId !== null && (
              <Button onClick={() => navigate(`/sales/einvoice/${invoiceId}`)}>
                {t('einvoice:view_invoice')}
              </Button>
            )}
            {isInvoiceable && invoiceId === null && (
              <Button
                type="primary"
                loading={actionLoading}
                onClick={handleGenerateInvoice}
              >
                {t('einvoice:generate_invoice')}
              </Button>
            )}
            {isCancellable && (
              <Button danger onClick={() => setCancelModal(true)}>
                {t('cancel')}
              </Button>
            )}
          </Space>
        }
      >
        <ProDescriptions column={3}>
          <ProDescriptions.Item label={t('customer')}>
            {so.customer_name || `#${so.customer_id}`}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('warehouse')}>
            {so.warehouse_name || `#${so.warehouse_id}`}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('business_date')}>{so.business_date}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('expected_ship_date')}>{so.expected_ship_date ?? '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('currency')}>{so.currency}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('payment_terms_days')}>{so.payment_terms_days}</ProDescriptions.Item>
          {so.shipping_address && (
            <ProDescriptions.Item label={t('shipping_address')} span={3}>{so.shipping_address}</ProDescriptions.Item>
          )}
          {so.remarks && <ProDescriptions.Item label={t('remarks')} span={3}>{so.remarks}</ProDescriptions.Item>}
          {so.cancel_reason && <ProDescriptions.Item label={t('cancel_reason')} span={3}>{so.cancel_reason}</ProDescriptions.Item>}
          {so.confirmed_at && <ProDescriptions.Item label={t('confirmed_at')}>{new Date(so.confirmed_at).toLocaleString('en-MY')}</ProDescriptions.Item>}
          {so.fully_shipped_at && <ProDescriptions.Item label={t('fully_shipped_at')}>{new Date(so.fully_shipped_at).toLocaleString('en-MY')}</ProDescriptions.Item>}
          {so.cancelled_at && <ProDescriptions.Item label={t('cancelled_at')}>{new Date(so.cancelled_at).toLocaleString('en-MY')}</ProDescriptions.Item>}
        </ProDescriptions>
      </Card>

      <Card title={t('lines')}>
        <Table
          dataSource={so.lines}
          columns={lineColumns}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 900 }}
        />
        <Row gutter={16} justify="end" style={{ marginTop: 16 }}>
          <Col><Typography.Text type="secondary">{t('subtotal_excl_tax')}:</Typography.Text> <Typography.Text>{fmt(so.subtotal_excl_tax)}</Typography.Text></Col>
          <Col><Typography.Text type="secondary">{t('tax_amount')}:</Typography.Text> <Typography.Text>{fmt(so.tax_amount)}</Typography.Text></Col>
          {parseFloat(so.shipping_amount) > 0 && (
            <Col><Typography.Text type="secondary">{t('shipping_amount')}:</Typography.Text> <Typography.Text>{fmt(so.shipping_amount)}</Typography.Text></Col>
          )}
          <Col><Typography.Text strong>{t('total_incl_tax')}:</Typography.Text> <Typography.Text strong>{fmt(so.total_incl_tax)}</Typography.Text></Col>
        </Row>
      </Card>

      <Modal
        title={t('cancel_title')}
        open={cancelModal}
        onOk={handleCancel}
        onCancel={() => { setCancelModal(false); setCancelReason('') }}
        confirmLoading={actionLoading}
        okButtonProps={{ danger: true }}
        okText={t('cancel')}
      >
        <Typography.Paragraph>{t('cancel_content')}</Typography.Paragraph>
        <textarea
          value={cancelReason}
          onChange={(e) => setCancelReason(e.target.value)}
          rows={3}
          style={{ width: '100%', padding: 8, borderRadius: 4, border: '1px solid #d9d9d9' }}
          placeholder={t('placeholders.cancelReason')}
        />
      </Modal>
    </Space>
  )
}
