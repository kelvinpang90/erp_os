import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import { Button, Card, Col, Modal, Row, Space, Spin, Table, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface POLine {
  id: number
  line_no: number
  sku_id: number
  uom_id: number
  description?: string
  qty_ordered: string
  qty_received: string
  unit_price_excl_tax: string
  tax_rate_percent: string
  discount_percent: string
  line_total_excl_tax: string
  line_total_incl_tax: string
}

interface PODetail {
  id: number
  document_no: string
  status: string
  supplier_id: number
  warehouse_id: number
  business_date: string
  expected_date?: string
  currency: string
  exchange_rate: string
  subtotal_excl_tax: string
  tax_amount: string
  discount_amount: string
  total_incl_tax: string
  payment_terms_days: number
  remarks?: string
  cancel_reason?: string
  confirmed_at?: string
  cancelled_at?: string
  created_at: string
  lines: POLine[]
}

const STATUS_COLOR: Record<string, string> = {
  DRAFT: 'default',
  CONFIRMED: 'blue',
  PARTIAL_RECEIVED: 'orange',
  FULLY_RECEIVED: 'green',
  CANCELLED: 'red',
}

export default function PODetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [po, setPO] = useState<PODetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [cancelModal, setCancelModal] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  const loadPO = () => {
    if (!id) return
    setLoading(true)
    axiosInstance
      .get(`/purchase-orders/${id}`)
      .then((res) => setPO(res.data))
      .catch(() => navigate('/purchase/orders'))
      .finally(() => setLoading(false))
  }

  useEffect(loadPO, [id])

  const handleConfirm = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      await axiosInstance.post(`/purchase-orders/${id}/confirm`)
      message.success('Purchase order confirmed. Stock incoming updated.')
      loadPO()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? 'Failed to confirm purchase order.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!id || !cancelReason.trim()) {
      message.warning('Please enter a cancellation reason.')
      return
    }
    setActionLoading(true)
    try {
      await axiosInstance.post(`/purchase-orders/${id}/cancel`, { cancel_reason: cancelReason })
      message.success('Purchase order cancelled.')
      setCancelModal(false)
      setCancelReason('')
      loadPO()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? 'Failed to cancel purchase order.')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
  if (!po) return null

  const fmt = (val: string) =>
    `${po.currency} ${parseFloat(val).toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  const lineColumns = [
    { title: '#', dataIndex: 'line_no', width: 50 },
    {
      title: 'SKU',
      dataIndex: 'sku_code',
      width: 260,
      render: (_: unknown, record: { sku_code?: string; sku_name?: string }) =>
        record.sku_code ? `${record.sku_code} — ${record.sku_name}` : '-',
    },
    { title: 'Description', dataIndex: 'description', ellipsis: true },
    { title: 'Qty Ordered', dataIndex: 'qty_ordered', width: 110, align: 'right' as const },
    { title: 'Qty Received', dataIndex: 'qty_received', width: 110, align: 'right' as const },
    { title: 'Unit Price', dataIndex: 'unit_price_excl_tax', width: 120, align: 'right' as const },
    { title: 'Tax %', dataIndex: 'tax_rate_percent', width: 70, align: 'right' as const },
    { title: 'Disc %', dataIndex: 'discount_percent', width: 70, align: 'right' as const },
    {
      title: 'Line Total (incl. tax)',
      dataIndex: 'line_total_incl_tax',
      width: 160,
      align: 'right' as const,
      render: (val: string) =>
        parseFloat(val).toLocaleString('en-MY', { minimumFractionDigits: 2 }),
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/purchase/orders')} />
            <Typography.Text strong>{po.document_no}</Typography.Text>
            <Tag color={STATUS_COLOR[po.status] ?? 'default'}>{po.status.replace(/_/g, ' ')}</Tag>
          </Space>
        }
        extra={
          <Space>
            {po.status === 'DRAFT' && (
              <>
                <Button onClick={() => navigate(`/purchase/orders/${id}/edit`)} icon={<EditOutlined />}>
                  Edit
                </Button>
                <Button type="primary" loading={actionLoading} onClick={handleConfirm}>
                  Confirm PO
                </Button>
              </>
            )}
            {(po.status === 'CONFIRMED' || po.status === 'PARTIAL_RECEIVED') && (
              <Button
                type="primary"
                onClick={() => navigate(`/purchase/goods-receipts/create?po_id=${id}`)}
              >
                Create Goods Receipt
              </Button>
            )}
            {(po.status === 'DRAFT' || po.status === 'CONFIRMED') && (
              <Button danger onClick={() => setCancelModal(true)}>
                Cancel PO
              </Button>
            )}
          </Space>
        }
      >
        <ProDescriptions column={3}>
          <ProDescriptions.Item label="Supplier ID">{po.supplier_id}</ProDescriptions.Item>
          <ProDescriptions.Item label="Warehouse ID">{po.warehouse_id}</ProDescriptions.Item>
          <ProDescriptions.Item label="Order Date">{po.business_date}</ProDescriptions.Item>
          <ProDescriptions.Item label="Expected Date">{po.expected_date ?? '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label="Currency">{po.currency}</ProDescriptions.Item>
          <ProDescriptions.Item label="Payment Terms">{po.payment_terms_days} days</ProDescriptions.Item>
          {po.remarks && <ProDescriptions.Item label="Remarks" span={3}>{po.remarks}</ProDescriptions.Item>}
          {po.cancel_reason && <ProDescriptions.Item label="Cancel Reason" span={3}>{po.cancel_reason}</ProDescriptions.Item>}
          {po.confirmed_at && <ProDescriptions.Item label="Confirmed At">{new Date(po.confirmed_at).toLocaleString('en-MY')}</ProDescriptions.Item>}
          {po.cancelled_at && <ProDescriptions.Item label="Cancelled At">{new Date(po.cancelled_at).toLocaleString('en-MY')}</ProDescriptions.Item>}
        </ProDescriptions>
      </Card>

      <Card title="Order Lines">
        <Table
          dataSource={po.lines}
          columns={lineColumns}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 900 }}
        />
        <Row gutter={16} justify="end" style={{ marginTop: 16 }}>
          <Col><Typography.Text type="secondary">Subtotal (excl. tax):</Typography.Text> <Typography.Text>{fmt(po.subtotal_excl_tax)}</Typography.Text></Col>
          <Col><Typography.Text type="secondary">Tax:</Typography.Text> <Typography.Text>{fmt(po.tax_amount)}</Typography.Text></Col>
          <Col><Typography.Text strong>Total (incl. tax):</Typography.Text> <Typography.Text strong>{fmt(po.total_incl_tax)}</Typography.Text></Col>
        </Row>
      </Card>

      <Modal
        title="Cancel Purchase Order"
        open={cancelModal}
        onOk={handleCancel}
        onCancel={() => { setCancelModal(false); setCancelReason('') }}
        confirmLoading={actionLoading}
        okButtonProps={{ danger: true }}
        okText="Cancel PO"
      >
        <Typography.Paragraph>Please provide a reason for cancellation:</Typography.Paragraph>
        <textarea
          value={cancelReason}
          onChange={(e) => setCancelReason(e.target.value)}
          rows={3}
          style={{ width: '100%', padding: 8, borderRadius: 4, border: '1px solid #d9d9d9' }}
          placeholder="e.g. Supplier unable to fulfill order"
        />
      </Modal>
    </Space>
  )
}
