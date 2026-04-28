import { ArrowLeftOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import { Button, Card, Space, Spin, Table, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface GRLine {
  id: number
  line_no: number
  purchase_order_line_id: number
  sku_id: number
  sku_code: string
  sku_name: string
  uom_id: number
  qty_ordered: string
  qty_already_received: string
  qty_received: string
  unit_cost: string
  batch_no?: string | null
  expiry_date?: string | null
  remarks?: string | null
  created_at: string
}

interface GRDetail {
  id: number
  document_no: string
  purchase_order_id: number
  purchase_order_no: string
  warehouse_id: number
  receipt_date: string
  delivery_note_no?: string | null
  received_by?: number | null
  remarks?: string | null
  created_by?: number | null
  created_at: string
  updated_at: string
  lines: GRLine[]
}

export default function GRDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation('goods_receipt')
  const [gr, setGR] = useState<GRDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    axiosInstance
      .get(`/goods-receipts/${id}`)
      .then((res) => setGR(res.data))
      .catch(() => {
        message.error('Goods receipt not found.')
        navigate('/purchase/goods-receipts')
      })
      .finally(() => setLoading(false))
  }, [id, navigate])

  if (loading)
    return (
      <Spin
        size="large"
        style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }}
      />
    )
  if (!gr) return null

  const fmt = (val: string) =>
    parseFloat(val || '0').toLocaleString('en-MY', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    })

  const totalQty = gr.lines.reduce(
    (sum, line) => sum + parseFloat(line.qty_received || '0'),
    0,
  )

  const lineColumns = [
    { title: '#', dataIndex: 'line_no', width: 50 },
    {
      title: t('sku'),
      dataIndex: 'sku_code',
      width: 260,
      render: (_: unknown, row: GRLine) =>
        row.sku_code ? `${row.sku_code} — ${row.sku_name}` : '-',
    },
    {
      title: t('qty_ordered'),
      dataIndex: 'qty_ordered',
      width: 110,
      align: 'right' as const,
      render: (val: string) => fmt(val),
    },
    {
      title: t('qty_received'),
      dataIndex: 'qty_received',
      width: 110,
      align: 'right' as const,
      render: (val: string) => fmt(val),
    },
    {
      title: t('unit_cost'),
      dataIndex: 'unit_cost',
      width: 120,
      align: 'right' as const,
      render: (val: string) => fmt(val),
    },
    {
      title: t('batch_no'),
      dataIndex: 'batch_no',
      width: 110,
      render: (val: string | null) => val ?? '—',
    },
    {
      title: t('expiry_date'),
      dataIndex: 'expiry_date',
      width: 120,
      render: (val: string | null) => val ?? '—',
    },
    {
      title: t('remarks'),
      dataIndex: 'remarks',
      ellipsis: true,
      render: (val: string | null) => val ?? '—',
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
              onClick={() => navigate('/purchase/goods-receipts')}
            />
            <Typography.Text strong>{gr.document_no}</Typography.Text>
          </Space>
        }
        extra={
          <Button
            onClick={() => navigate(`/purchase/orders/${gr.purchase_order_id}`)}
          >
            View PO
          </Button>
        }
      >
        <ProDescriptions column={3}>
          <ProDescriptions.Item label={t('purchase_order_no')}>
            {gr.purchase_order_no}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('receipt_date')}>
            {gr.receipt_date}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('warehouse')}>
            #{gr.warehouse_id}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('delivery_note_no')}>
            {gr.delivery_note_no ?? '—'}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('received_by')}>
            {gr.received_by ? `User #${gr.received_by}` : '—'}
          </ProDescriptions.Item>
          <ProDescriptions.Item label="Created At">
            {new Date(gr.created_at).toLocaleString('en-MY')}
          </ProDescriptions.Item>
          {gr.remarks && (
            <ProDescriptions.Item label={t('remarks')} span={3}>
              {gr.remarks}
            </ProDescriptions.Item>
          )}
        </ProDescriptions>
      </Card>

      <Card title={t('lines')}>
        <Table
          dataSource={gr.lines}
          columns={lineColumns}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 1100 }}
          summary={() => (
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={3} align="right">
                <Typography.Text strong>Total Qty Received:</Typography.Text>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={1} align="right">
                <Typography.Text strong>
                  {totalQty.toLocaleString('en-MY', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 4,
                  })}
                </Typography.Text>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={2} colSpan={5} />
            </Table.Summary.Row>
          )}
        />
      </Card>
    </Space>
  )
}
