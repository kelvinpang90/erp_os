import { Button, Card, Empty, Select, Space, Spin, Table, Typography, message } from 'antd'
import type { ColumnsType, TableRowSelection } from 'antd/es/table/interface'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface LowStockAlert {
  sku_id: number
  sku_code: string
  sku_name: string
  sku_name_zh?: string | null
  warehouse_id: number
  warehouse_code: string
  warehouse_name: string
  available: string
  safety_stock: string
  reorder_point: string
  reorder_qty: string
  shortage: string
  suggested_qty: string
}

interface AlertResponse {
  items: LowStockAlert[]
  total: number
}

interface WarehouseOption {
  value: number
  label: string
}

export default function AlertPage() {
  const { t } = useTranslation('inventory')
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState<LowStockAlert[]>([])
  const [loading, setLoading] = useState(false)
  const [warehouseId, setWarehouseId] = useState<number | undefined>(undefined)
  const [selectedKeys, setSelectedKeys] = useState<React.Key[]>([])
  const [warehouseOptions, setWarehouseOptions] = useState<WarehouseOption[]>([])

  useEffect(() => {
    axiosInstance
      .get<{ items: { id: number; code: string; name: string }[] }>('/warehouses?page_size=50')
      .then((res) => {
        setWarehouseOptions(
          res.data.items.map((w) => ({ value: w.id, label: `${w.code} — ${w.name}` })),
        )
      })
      .catch(() => {/* warehouse filter is optional, fail silently */})
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const params = new URLSearchParams()
    if (warehouseId !== undefined) params.set('warehouse_id', String(warehouseId))
    axiosInstance
      .get<AlertResponse>(`/inventory/alerts/low-stock?${params}`)
      .then((res) => {
        if (!cancelled) {
          setAlerts(res.data.items)
          setSelectedKeys([])
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [warehouseId])

  const handleGeneratePO = () => {
    if (selectedKeys.length === 0) {
      message.warning(t('alerts.actions.selectAtLeastOne'))
      return
    }
    const selected = alerts.filter((a) => selectedKeys.includes(`${a.sku_id}-${a.warehouse_id}`))
    // Pre-fill all selected lines into a single PO. Suppliers and the
    // destination warehouse are decided in the PO editor; if the user picked
    // alerts spanning multiple warehouses we pick the first as a hint.
    const warehouseIdHint = selected[0]?.warehouse_id
    const lines = selected.map((a) => ({
      sku_id: a.sku_id,
      qty: parseFloat(a.suggested_qty),
    }))
    navigate('/purchase/orders/create', {
      state: {
        restockPrefill: {
          warehouse_id: warehouseIdHint,
          lines,
        },
      },
    })
  }

  const columns = useMemo<ColumnsType<LowStockAlert>>(
    () => [
      {
        title: t('alerts.columns.sku'),
        key: 'sku',
        render: (_, row) => (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{row.sku_code}</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {row.sku_name}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: t('alerts.columns.warehouse'),
        dataIndex: 'warehouse_name',
        render: (_, row) => `${row.warehouse_code} — ${row.warehouse_name}`,
      },
      {
        title: t('alerts.columns.available'),
        dataIndex: 'available',
        align: 'right',
        render: (v: string) => Number(v).toLocaleString(),
      },
      {
        title: t('alerts.columns.safetyStock'),
        dataIndex: 'safety_stock',
        align: 'right',
        render: (v: string) => Number(v).toLocaleString(),
      },
      {
        title: t('alerts.columns.shortage'),
        dataIndex: 'shortage',
        align: 'right',
        render: (v: string) => (
          <Typography.Text type="danger" strong>
            {Number(v).toLocaleString()}
          </Typography.Text>
        ),
      },
      {
        title: t('alerts.columns.suggestedQty'),
        dataIndex: 'suggested_qty',
        align: 'right',
        render: (v: string) => (
          <Typography.Text strong>{Number(v).toLocaleString()}</Typography.Text>
        ),
      },
    ],
    [t],
  )

  const rowSelection: TableRowSelection<LowStockAlert> = {
    selectedRowKeys: selectedKeys,
    onChange: setSelectedKeys,
  }

  return (
    <Card
      title={t('alerts.title')}
      extra={
        <Space>
          <Select
            style={{ width: 240 }}
            placeholder={t('alerts.warehouseFilter')}
            allowClear
            options={warehouseOptions}
            value={warehouseId}
            onChange={(v) => setWarehouseId(v)}
          />
          <Button type="primary" disabled={selectedKeys.length === 0} onClick={handleGeneratePO}>
            {t('alerts.actions.generatePo')}
          </Button>
        </Space>
      }
    >
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        {t('alerts.subtitle')}
      </Typography.Paragraph>
      <Spin spinning={loading}>
        {alerts.length > 0 ? (
          <Table<LowStockAlert>
            rowKey={(row) => `${row.sku_id}-${row.warehouse_id}`}
            dataSource={alerts}
            columns={columns}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            rowSelection={rowSelection}
            size="middle"
          />
        ) : (
          !loading && <Empty description={t('alerts.empty')} />
        )}
      </Spin>
    </Card>
  )
}
