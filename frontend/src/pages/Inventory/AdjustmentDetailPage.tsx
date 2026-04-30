import { ArrowLeftOutlined } from '@ant-design/icons'
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

interface AdjustmentLine {
  id: number
  line_no: number
  sku_id: number
  sku_code: string
  sku_name: string
  qty_before: string
  qty_after: string
  qty_diff: string
  unit_cost?: string
  batch_no?: string
  notes?: string
}

interface AdjustmentDetail {
  id: number
  document_no: string
  status: string
  warehouse_id: number
  warehouse_name: string
  business_date: string
  reason: string
  reason_description?: string
  remarks?: string
  approved_at?: string
  approved_by?: number
  lines: AdjustmentLine[]
}

const STATUS_COLOR: Record<string, string> = {
  DRAFT: 'default',
  CONFIRMED: 'green',
  CANCELLED: 'red',
}

export default function AdjustmentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation('stock_adjustment')
  const [adj, setAdj] = useState<AdjustmentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [cancelModal, setCancelModal] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  const load = () => {
    if (!id) return
    setLoading(true)
    axiosInstance
      .get(`/stock-adjustments/${id}`)
      .then((res) => setAdj(res.data))
      .catch(() => navigate('/inventory/adjustments'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [id])

  const handleConfirm = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      await axiosInstance.post(`/stock-adjustments/${id}/confirm`)
      message.success(t('confirm'))
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? t('manager_only_warning'))
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
      await axiosInstance.post(`/stock-adjustments/${id}/cancel`, {
        cancel_reason: cancelReason,
      })
      message.success(t('cancel'))
      setCancelModal(false)
      setCancelReason('')
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? 'Failed to cancel')
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
  if (!adj) return null

  const lineColumns = [
    { title: t('line_no'), dataIndex: 'line_no', width: 60 },
    {
      title: t('sku'),
      dataIndex: 'sku_code',
      width: 280,
      render: (_: unknown, row: AdjustmentLine) =>
        row.sku_code ? `${row.sku_code} — ${row.sku_name}` : '-',
    },
    { title: t('qty_before'), dataIndex: 'qty_before', width: 110, align: 'right' as const },
    { title: t('qty_after'), dataIndex: 'qty_after', width: 110, align: 'right' as const },
    {
      title: t('qty_diff'),
      dataIndex: 'qty_diff',
      width: 110,
      align: 'right' as const,
      render: (val: string | undefined) => {
        if (val === undefined || val === null) return '—'
        const n = parseFloat(val)
        return (
          <span style={{ color: n > 0 ? '#52c41a' : n < 0 ? '#ff4d4f' : undefined }}>
            {n > 0 ? `+${n}` : n}
          </span>
        )
      },
    },
    {
      title: t('unit_cost'),
      dataIndex: 'unit_cost',
      width: 110,
      align: 'right' as const,
      render: (val: string | undefined) => val ?? '—',
    },
    { title: t('batch_no'), dataIndex: 'batch_no', width: 100, render: (v: string | undefined) => v ?? '—' },
    { title: t('notes'), dataIndex: 'notes', ellipsis: true },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              type="text"
              onClick={() => navigate('/inventory/adjustments')}
            />
            <Typography.Text strong>{adj.document_no}</Typography.Text>
            <Tag color={STATUS_COLOR[adj.status] ?? 'default'}>
              {t(`status_${adj.status}`)}
            </Tag>
          </Space>
        }
        extra={
          <Space>
            {adj.status === 'DRAFT' && (
              <>
                <Button type="primary" loading={actionLoading} onClick={handleConfirm}>
                  {t('confirm')}
                </Button>
                <Button danger onClick={() => setCancelModal(true)}>
                  {t('cancel')}
                </Button>
              </>
            )}
          </Space>
        }
      >
        <ProDescriptions column={3}>
          <ProDescriptions.Item label={t('warehouse')}>
            {adj.warehouse_name || `#${adj.warehouse_id}`}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('business_date')}>
            {adj.business_date}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('reason')}>
            {t(`reason_${adj.reason}`)}
          </ProDescriptions.Item>
          {adj.reason_description && (
            <ProDescriptions.Item label={t('reason_description')} span={3}>
              {adj.reason_description}
            </ProDescriptions.Item>
          )}
          {adj.remarks && (
            <ProDescriptions.Item label={t('remarks')} span={3}>
              {adj.remarks}
            </ProDescriptions.Item>
          )}
          {adj.approved_at && (
            <ProDescriptions.Item label={t('approved_at')}>
              {new Date(adj.approved_at).toLocaleString('en-MY')}
            </ProDescriptions.Item>
          )}
        </ProDescriptions>
      </Card>

      <Card title={t('lines')}>
        <Table
          dataSource={adj.lines}
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
