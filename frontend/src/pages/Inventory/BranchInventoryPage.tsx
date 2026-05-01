import { Card, Empty, Input, Pagination, Space, Spin, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import StockStatusBadge from '../../components/StockStatusBadge'

interface WarehouseHeader {
  id: number
  code: string
  name: string
}

interface WarehouseStockCell {
  warehouse_id: number
  warehouse_code: string
  warehouse_name: string
  on_hand: string
  reserved: string
  quality_hold: string
  available: string
  incoming: string
  in_transit: string
}

interface BranchInventoryRow {
  sku_id: number
  sku_code: string
  sku_name: string
  sku_name_zh?: string | null
  safety_stock: string
  reorder_point: string
  reorder_qty: string
  warehouses: WarehouseStockCell[]
}

interface MatrixResponse {
  warehouses: WarehouseHeader[]
  rows: BranchInventoryRow[]
  total_skus: number
}

const PAGE_SIZE = 50

function colorForRatio(available: number, safety: number): string {
  // No safety policy → neutral grey.
  if (safety <= 0) return '#f5f5f5'
  if (available <= 0) return '#ff4d4f' // red — out of stock
  const ratio = available / safety
  if (ratio < 0.5) return '#ff7a45'    // orange — critical
  if (ratio < 1) return '#ffd666'      // yellow — warning
  if (ratio < 1.5) return '#b7eb8f'    // light green — healthy
  return '#52c41a'                     // green — abundant
}

function textColorForBg(bg: string): string {
  // The two darker greens benefit from white text; everything else stays dark.
  return bg === '#52c41a' || bg === '#ff4d4f' ? '#fff' : 'rgba(0, 0, 0, 0.85)'
}

export default function BranchInventoryPage() {
  const { t } = useTranslation('inventory')
  const [data, setData] = useState<MatrixResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [skuQuery, setSkuQuery] = useState('')
  const [page, setPage] = useState(1)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
    if (skuQuery.trim()) params.set('sku_query', skuQuery.trim())
    axiosInstance
      .get<MatrixResponse>(`/inventory/branch-matrix?${params}`)
      .then((res) => {
        if (!cancelled) setData(res.data)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [page, skuQuery])

  const columns = useMemo<ColumnsType<BranchInventoryRow>>(() => {
    const baseCols: ColumnsType<BranchInventoryRow> = [
      {
        title: t('branchMatrix.columns.sku'),
        dataIndex: 'sku_code',
        width: 130,
        fixed: 'left',
      },
      {
        title: t('branchMatrix.columns.name'),
        dataIndex: 'sku_name',
        width: 220,
        fixed: 'left',
        ellipsis: true,
      },
      {
        title: t('branchMatrix.columns.safetyStock'),
        dataIndex: 'safety_stock',
        width: 110,
        align: 'right',
        render: (v: string) => Number(v).toLocaleString(),
      },
    ]

    const warehouseCols: ColumnsType<BranchInventoryRow> = (data?.warehouses ?? []).map((wh) => ({
      title: (
        <Tooltip title={wh.name}>
          <span>{wh.code}</span>
        </Tooltip>
      ),
      key: `wh-${wh.id}`,
      width: 110,
      align: 'center',
      render: (_v, row) => {
        const cell = row.warehouses.find((c) => c.warehouse_id === wh.id)
        if (!cell) return null
        const safety = Number(row.safety_stock)
        const available = Number(cell.available)
        const bg = colorForRatio(available, safety)
        const fg = textColorForBg(bg)
        return (
          <Tooltip
            title={<StockStatusBadge stock={cell} />}
            color="white"
            overlayInnerStyle={{ color: 'rgba(0,0,0,0.85)' }}
          >
            <div
              style={{
                background: bg,
                color: fg,
                padding: '6px 4px',
                borderRadius: 4,
                fontWeight: 600,
                cursor: 'help',
              }}
            >
              {Number(cell.available).toLocaleString()}
            </div>
          </Tooltip>
        )
      },
    }))

    return [...baseCols, ...warehouseCols]
  }, [data, t])

  return (
    <Card
      title={t('branchMatrix.title')}
      extra={
        <Input.Search
          placeholder={t('branchMatrix.searchPlaceholder')}
          allowClear
          style={{ width: 280 }}
          onSearch={(v) => {
            setPage(1)
            setSkuQuery(v)
          }}
        />
      }
    >
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        {t('branchMatrix.subtitle')}
      </Typography.Paragraph>

      <Space size="small" wrap style={{ marginBottom: 12 }}>
        <Tag color="green">{t('branchMatrix.legend.abundant')}</Tag>
        <Tag color="lime">{t('branchMatrix.legend.healthy')}</Tag>
        <Tag color="gold">{t('branchMatrix.legend.warning')}</Tag>
        <Tag color="orange">{t('branchMatrix.legend.critical')}</Tag>
        <Tag color="red">{t('branchMatrix.legend.depleted')}</Tag>
        <Tag>{t('branchMatrix.legend.unmanaged')}</Tag>
      </Space>

      <Spin spinning={loading}>
        {data && data.rows.length > 0 ? (
          <>
            <Table<BranchInventoryRow>
              rowKey="sku_id"
              dataSource={data.rows}
              columns={columns}
              pagination={false}
              scroll={{ x: 'max-content' }}
              size="small"
            />
            <Pagination
              style={{ marginTop: 16, textAlign: 'right' }}
              current={page}
              pageSize={PAGE_SIZE}
              total={data.total_skus}
              showSizeChanger={false}
              onChange={setPage}
            />
          </>
        ) : (
          !loading && <Empty description={t('branchMatrix.empty')} />
        )}
      </Spin>
    </Card>
  )
}
