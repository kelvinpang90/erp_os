import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { getAdjustmentColumns, type AdjustmentRow } from './adjustmentColumns'

async function fetchAdjustments(params: {
  current?: number
  pageSize?: number
  document_no?: string
  status?: string
}) {
  const { current = 1, pageSize = 20, document_no, status } = params
  const query = new URLSearchParams({
    page: String(current),
    page_size: String(pageSize),
  })
  if (document_no) query.set('search', document_no)
  if (status) query.set('status', status)
  const res = await axiosInstance.get(`/stock-adjustments?${query}`)
  return res.data
}

export default function AdjustmentListPage() {
  const navigate = useNavigate()
  const { t } = useTranslation('stock_adjustment')

  const [warehouseMap, setWarehouseMap] = useState<Map<number, string>>(new Map())

  useEffect(() => {
    axiosInstance
      .get('/warehouses?page_size=100')
      .then((res) => {
        const map = new Map<number, string>()
        for (const w of res.data.items as { id: number; name: string }[]) {
          map.set(w.id, w.name)
        }
        setWarehouseMap(map)
      })
      .catch(() => {/* fall back to "#id" rendering */})
  }, [])

  const columns = useMemo(
    () => [
      ...getAdjustmentColumns(warehouseMap),
      {
        title: t('actions'),
        valueType: 'option' as const,
        fixed: 'right' as const,
        width: 100,
        render: (_: unknown, row: AdjustmentRow) => [
          <a
            key="view"
            onClick={() => navigate(`/inventory/adjustments/${row.id}`)}
          >
            {t('view', { defaultValue: 'View' })}
          </a>,
        ],
      },
    ],
    [warehouseMap, navigate, t],
  )

  return (
    <ResourceListPage<AdjustmentRow>
      title={t('title')}
      columns={columns}
      fetchData={fetchAdjustments}
      createPath="/inventory/adjustments/new"
    />
  )
}
