import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import {
  Button,
  Card,
  Modal,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface TransferLine {
  id: number
  line_no: number
  sku_id: number
  sku_code: string
  sku_name: string
  uom_id: number
  qty_sent: string
  qty_received: string
  unit_cost_snapshot?: string
  batch_no?: string
  expiry_date?: string
}

interface TransferDetail {
  id: number
  document_no: string
  status: string
  from_warehouse_id: number
  from_warehouse_name: string
  to_warehouse_id: number
  to_warehouse_name: string
  business_date: string
  expected_arrival_date?: string
  actual_arrival_date?: string
  remarks?: string
  created_at: string
  lines: TransferLine[]
}

const STATUS_COLOR: Record<string, string> = {
  DRAFT: 'default',
  CONFIRMED: 'blue',
  IN_TRANSIT: 'gold',
  RECEIVED: 'green',
  CANCELLED: 'red',
}

export default function TransferDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation('stock_transfer')
  const [transfer, setTransfer] = useState<TransferDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [cancelModal, setCancelModal] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  const load = () => {
    if (!id) return
    setLoading(true)
    axiosInstance
      .get(`/stock-transfers/${id}`)
      .then((res) => setTransfer(res.data))
      .catch(() => navigate('/inventory/transfers'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [id])

  const handleConfirm = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      await axiosInstance.post(`/stock-transfers/${id}/confirm`)
      message.success(t('confirm'))
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? 'Failed to confirm transfer')
    } finally {
      setActionLoading(false)
    }
  }

  const handleShipOut = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      await axiosInstance.post(`/stock-transfers/${id}/ship-out`)
      message.success(t('ship_out'))
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? 'Failed to ship transfer')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!id || !cancelReason.trim()) {
      message.warning(t('cancel_content'))
      return
    }
    setActionLoading(true)
    try {
      await axiosInstance.post(`/stock-transfers/${id}/cancel`, {
        cancel_reason: cancelReason,
      })
      message.success(t('cancel'))
      setCancelModal(false)
      setCancelReason('')
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? 'Failed to cancel transfer')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading)
    return (
      <Spin
        size="large"
        style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }}
      />
    )
  if (!transfer) return null

  const lineColumns = [
    { title: t('line_no'), dataIndex: 'line_no', width: 50 },
    {
      title: t('sku'),
      dataIndex: 'sku_code',
      width: 260,
      render: (_: unknown, record: TransferLine) =>
        record.sku_code ? `${record.sku_code} — ${record.sku_name}` : '-',
    },
    {
      title: t('qty_sent'),
      dataIndex: 'qty_sent',
      width: 110,
      align: 'right' as const,
    },
    {
      title: t('qty_received'),
      dataIndex: 'qty_received',
      width: 110,
      align: 'right' as const,
    },
    {
      title: t('unit_cost_snapshot'),
      dataIndex: 'unit_cost_snapshot',
      width: 140,
      align: 'right' as const,
      render: (val: string | undefined) => val ?? '—',
    },
    { title: t('batch_no'), dataIndex: 'batch_no', width: 100, render: (v: string | undefined) => v ?? '—' },
    { title: t('expiry_date'), dataIndex: 'expiry_date', width: 110, render: (v: string | undefined) => v ?? '—' },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              type="text"
              onClick={() => navigate('/inventory/transfers')}
            />
            <Typography.Text strong>{transfer.document_no}</Typography.Text>
            <Tag color={STATUS_COLOR[transfer.status] ?? 'default'}>
              {t(`status_${transfer.status}`)}
            </Tag>
          </Space>
        }
        extra={
          <Space>
            {transfer.status === 'DRAFT' && (
              <>
                <Button
                  onClick={() => navigate(`/inventory/transfers/${id}/edit`)}
                  icon={<EditOutlined />}
                >
                  {t('edit')}
                </Button>
                <Button type="primary" loading={actionLoading} onClick={handleConfirm}>
                  {t('confirm')}
                </Button>
              </>
            )}
            {transfer.status === 'CONFIRMED' && (
              <Button type="primary" loading={actionLoading} onClick={handleShipOut}>
                {t('ship_out')}
              </Button>
            )}
            {transfer.status === 'IN_TRANSIT' && (
              <Button
                type="primary"
                onClick={() => navigate(`/inventory/transfers/${id}/receive`)}
              >
                {t('receive')}
              </Button>
            )}
            {(transfer.status === 'DRAFT' || transfer.status === 'CONFIRMED') && (
              <Button danger onClick={() => setCancelModal(true)}>
                {t('cancel')}
              </Button>
            )}
          </Space>
        }
      >
        <ProDescriptions column={3}>
          <ProDescriptions.Item label={t('from_warehouse')}>
            {transfer.from_warehouse_name || `#${transfer.from_warehouse_id}`}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('to_warehouse')}>
            {transfer.to_warehouse_name || `#${transfer.to_warehouse_id}`}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('business_date')}>
            {transfer.business_date}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('expected_arrival_date')}>
            {transfer.expected_arrival_date ?? '—'}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('actual_arrival_date')}>
            {transfer.actual_arrival_date ?? '—'}
          </ProDescriptions.Item>
          {transfer.remarks && (
            <ProDescriptions.Item label={t('remarks')} span={3}>
              {transfer.remarks}
            </ProDescriptions.Item>
          )}
        </ProDescriptions>
      </Card>

      <Card title={t('lines')}>
        <Table
          dataSource={transfer.lines}
          columns={lineColumns}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 900 }}
        />
      </Card>

      <Modal
        title={t('cancel_title')}
        open={cancelModal}
        onOk={handleCancel}
        onCancel={() => {
          setCancelModal(false)
          setCancelReason('')
        }}
        confirmLoading={actionLoading}
        okButtonProps={{ danger: true }}
        okText={t('cancel')}
      >
        <Typography.Paragraph>{t('cancel_content')}</Typography.Paragraph>
        <textarea
          value={cancelReason}
          onChange={(e) => setCancelReason(e.target.value)}
          rows={3}
          style={{
            width: '100%',
            padding: 8,
            borderRadius: 4,
            border: '1px solid #d9d9d9',
          }}
        />
      </Modal>
    </Space>
  )
}
