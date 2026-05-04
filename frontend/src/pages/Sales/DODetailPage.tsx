import { ArrowLeftOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import { Button, Card, Space, Spin, Table, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface DOLine {
  id: number
  line_no: number
  sales_order_line_id: number
  sku_id: number
  sku_code: string
  sku_name: string
  uom_id: number
  qty_ordered: string
  qty_already_shipped: string
  qty_shipped: string
  batch_no?: string | null
  expiry_date?: string | null
  serial_no?: string | null
  created_at: string
}

interface DODetail {
  id: number
  document_no: string
  sales_order_id: number
  sales_order_no: string
  warehouse_id: number
  warehouse_name: string
  delivery_date: string
  shipping_method?: string | null
  tracking_no?: string | null
  delivered_by?: number | null
  delivered_by_name: string
  remarks?: string | null
  created_by?: number | null
  created_at: string
  updated_at: string
  lines: DOLine[]
}

export default function DODetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation(['delivery_order', 'common'])
  const [doc, setDoc] = useState<DODetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    axiosInstance
      .get(`/delivery-orders/${id}`)
      .then((res) => setDoc(res.data))
      .catch(() => {
        message.error(t('messages.notFound'))
        navigate('/sales/delivery')
      })
      .finally(() => setLoading(false))
  }, [id, navigate, t])

  if (loading)
    return (
      <Spin
        size="large"
        style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }}
      />
    )
  if (!doc) return null

  const fmt = (val: string) =>
    parseFloat(val || '0').toLocaleString('en-MY', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    })

  const totalQty = doc.lines.reduce(
    (sum, line) => sum + parseFloat(line.qty_shipped || '0'),
    0,
  )

  const lineColumns = [
    { title: '#', dataIndex: 'line_no', width: 50 },
    {
      title: t('sku'),
      dataIndex: 'sku_code',
      width: 260,
      render: (_: unknown, row: DOLine) =>
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
      title: t('qty_shipped'),
      dataIndex: 'qty_shipped',
      width: 110,
      align: 'right' as const,
      render: (val: string) => fmt(val),
    },
    {
      title: t('batch_no'),
      dataIndex: 'batch_no',
      width: 120,
      render: (val: string | null) => val ?? '—',
    },
    {
      title: t('expiry_date'),
      dataIndex: 'expiry_date',
      width: 120,
      render: (val: string | null) => val ?? '—',
    },
    {
      title: t('serial_no'),
      dataIndex: 'serial_no',
      width: 140,
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
              onClick={() => navigate('/sales/delivery')}
            />
            <Typography.Text strong>{doc.document_no}</Typography.Text>
          </Space>
        }
        extra={
          <Button onClick={() => navigate(`/sales/orders/${doc.sales_order_id}`)}>
            {t('buttons.viewSo')}
          </Button>
        }
      >
        <ProDescriptions column={3}>
          <ProDescriptions.Item label={t('sales_order')}>
            {doc.sales_order_no}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('delivery_date')}>
            {doc.delivery_date}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('warehouse')}>
            {doc.warehouse_name || `#${doc.warehouse_id}`}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('shipping_method')}>
            {doc.shipping_method ?? '—'}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('tracking_no')}>
            {doc.tracking_no ?? '—'}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('delivered_by')}>
            {doc.delivered_by_name || (doc.delivered_by ? `User #${doc.delivered_by}` : '—')}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('common:createdAt')}>
            {new Date(doc.created_at).toLocaleString('en-MY')}
          </ProDescriptions.Item>
          {doc.remarks && (
            <ProDescriptions.Item label={t('remarks')} span={3}>
              {doc.remarks}
            </ProDescriptions.Item>
          )}
        </ProDescriptions>
      </Card>

      <Card title={t('lines')}>
        <Table
          dataSource={doc.lines}
          columns={lineColumns}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 900 }}
          summary={() => (
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={3} align="right">
                <Typography.Text strong>{t('summaryTotal')}:</Typography.Text>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={1} align="right">
                <Typography.Text strong>
                  {totalQty.toLocaleString('en-MY', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 4,
                  })}
                </Typography.Text>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={2} colSpan={3} />
            </Table.Summary.Row>
          )}
        />
      </Card>
    </Space>
  )
}
