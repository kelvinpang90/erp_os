import { ArrowLeftOutlined } from '@ant-design/icons'
import { App, Button, Card, InputNumber, Skeleton, Space, Table, Typography } from 'antd'
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
  qty_sent: string
  qty_received: string
}

interface TransferDetail {
  id: number
  document_no: string
  status: string
  lines: TransferLine[]
}

export default function TransferReceivePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation('stock_transfer')
  const [transfer, setTransfer] = useState<TransferDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [qtyMap, setQtyMap] = useState<Record<number, number>>({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!id) return
    axiosInstance
      .get(`/stock-transfers/${id}`)
      .then((res) => {
        if (res.data.status !== 'IN_TRANSIT') {
          message.error(t('messages.only_in_transit_receivable'))
          navigate(`/inventory/transfers/${id}`)
          return
        }
        setTransfer(res.data)
      })
      .catch(() => navigate('/inventory/transfers'))
      .finally(() => setLoading(false))
  }, [id, navigate, message, t])

  const handleSubmit = async () => {
    if (!id || !transfer) return
    const payloadLines = Object.entries(qtyMap)
      .filter(([, qty]) => qty > 0)
      .map(([lineId, qty]) => ({ line_id: Number(lineId), qty_received: qty }))

    if (payloadLines.length === 0) {
      message.warning(t('receive'))
      return
    }
    setSubmitting(true)
    try {
      await axiosInstance.post(`/stock-transfers/${id}/receive`, { lines: payloadLines })
      message.success(t('receive'))
      navigate(`/inventory/transfers/${id}`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? t('messages.receive_failed'))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <Skeleton active />
  if (!transfer) return null

  const columns = [
    { title: t('line_no'), dataIndex: 'line_no', width: 60 },
    {
      title: t('sku'),
      dataIndex: 'sku_code',
      width: 280,
      render: (_: unknown, record: TransferLine) =>
        record.sku_code ? `${record.sku_code} — ${record.sku_name}` : '-',
    },
    {
      title: t('qty_sent'),
      dataIndex: 'qty_sent',
      width: 100,
      align: 'right' as const,
    },
    {
      title: t('qty_received'),
      dataIndex: 'qty_received',
      width: 110,
      align: 'right' as const,
    },
    {
      title: t('qty_remaining'),
      width: 100,
      align: 'right' as const,
      render: (_: unknown, record: TransferLine) =>
        (parseFloat(record.qty_sent) - parseFloat(record.qty_received)).toLocaleString(),
    },
    {
      title: t('receive_now'),
      width: 140,
      render: (_: unknown, record: TransferLine) => {
        const remaining = parseFloat(record.qty_sent) - parseFloat(record.qty_received)
        return (
          <InputNumber
            min={0}
            max={remaining}
            step={1}
            value={qtyMap[record.id] ?? 0}
            onChange={(val) =>
              setQtyMap((prev) => ({ ...prev, [record.id]: Number(val ?? 0) }))
            }
          />
        )
      },
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
              onClick={() => navigate(`/inventory/transfers/${id}`)}
            />
            <Typography.Text strong>{transfer.document_no}</Typography.Text>
            <Typography.Text type="secondary">— {t('receive_title')}</Typography.Text>
          </Space>
        }
        extra={
          <Button type="primary" loading={submitting} onClick={handleSubmit}>
            {t('receive')}
          </Button>
        }
      >
        <Typography.Paragraph type="secondary">{t('receive_content')}</Typography.Paragraph>
        <Table
          rowKey="id"
          dataSource={transfer.lines}
          columns={columns}
          pagination={false}
          size="small"
          scroll={{ x: 900 }}
        />
      </Card>
    </Space>
  )
}
