import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import { Button, Card, Col, Modal, Row, Space, Spin, Table, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface POLine {
  id: number
  line_no: number
  sku_id: number
  sku_code?: string
  sku_name?: string
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
  supplier_name: string
  warehouse_id: number
  warehouse_name: string
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
  const { t } = useTranslation(['purchase_order', 'common'])
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
      message.success(t('messages.confirmed'))
      loadPO()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? t('messages.confirmFailed'))
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
      await axiosInstance.post(`/purchase-orders/${id}/cancel`, { cancel_reason: cancelReason })
      message.success(t('messages.cancelled'))
      setCancelModal(false)
      setCancelReason('')
      loadPO()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? t('messages.cancelFailed'))
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
  if (!po) return null

  const fmt = (val: string) =>
    `${po.currency} ${parseFloat(val).toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  const lineColumns: import('antd/es/table').ColumnsType<POLine> = [
    { title: '#', dataIndex: 'line_no', width: 50 },
    {
      title: t('sku'),
      dataIndex: 'sku_code',
      width: 260,
      render: (_: unknown, record: POLine) =>
        record.sku_code ? `${record.sku_code} — ${record.sku_name}` : '-',
    },
    { title: t('description'), dataIndex: 'description', ellipsis: true },
    { title: t('qty_ordered'), dataIndex: 'qty_ordered', width: 110, align: 'right' as const },
    { title: t('qty_received'), dataIndex: 'qty_received', width: 110, align: 'right' as const },
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
                  {t('common:edit')}
                </Button>
                <Button type="primary" loading={actionLoading} onClick={handleConfirm}>
                  {t('confirm')}
                </Button>
              </>
            )}
            {(po.status === 'CONFIRMED' || po.status === 'PARTIAL_RECEIVED') && (
              <Button
                type="primary"
                onClick={() => navigate(`/purchase/goods-receipts/create?po_id=${id}`)}
              >
                {t('buttons.createGoodsReceipt')}
              </Button>
            )}
            {(po.status === 'DRAFT' || po.status === 'CONFIRMED') && (
              <Button danger onClick={() => setCancelModal(true)}>
                {t('cancel')}
              </Button>
            )}
          </Space>
        }
      >
        <ProDescriptions column={3}>
          <ProDescriptions.Item label={t('supplier')}>
            {po.supplier_name || `#${po.supplier_id}`}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('warehouse')}>
            {po.warehouse_name || `#${po.warehouse_id}`}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('business_date')}>{po.business_date}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('expected_date')}>{po.expected_date ?? '—'}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('currency')}>{po.currency}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('payment_terms_days')}>{po.payment_terms_days}</ProDescriptions.Item>
          {po.remarks && <ProDescriptions.Item label={t('remarks')} span={3}>{po.remarks}</ProDescriptions.Item>}
          {po.cancel_reason && <ProDescriptions.Item label={t('cancel_reason')} span={3}>{po.cancel_reason}</ProDescriptions.Item>}
          {po.confirmed_at && <ProDescriptions.Item label={t('confirmed_at')}>{new Date(po.confirmed_at).toLocaleString('en-MY')}</ProDescriptions.Item>}
          {po.cancelled_at && <ProDescriptions.Item label={t('cancelled_at')}>{new Date(po.cancelled_at).toLocaleString('en-MY')}</ProDescriptions.Item>}
        </ProDescriptions>
      </Card>

      <Card title={t('lines')}>
        <Table
          dataSource={po.lines}
          columns={lineColumns}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 900 }}
        />
        <Row gutter={16} justify="end" style={{ marginTop: 16 }}>
          <Col><Typography.Text type="secondary">{t('subtotal_excl_tax')}:</Typography.Text> <Typography.Text>{fmt(po.subtotal_excl_tax)}</Typography.Text></Col>
          <Col><Typography.Text type="secondary">{t('tax_amount')}:</Typography.Text> <Typography.Text>{fmt(po.tax_amount)}</Typography.Text></Col>
          <Col><Typography.Text strong>{t('total_incl_tax')}:</Typography.Text> <Typography.Text strong>{fmt(po.total_incl_tax)}</Typography.Text></Col>
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
