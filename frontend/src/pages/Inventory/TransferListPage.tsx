import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { getTransferColumns, type TransferRow } from './transferColumns'

async function fetchTransfers(params: {
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
  const res = await axiosInstance.get(`/stock-transfers?${query}`)
  return res.data
}

export default function TransferListPage() {
  const navigate = useNavigate()
  const { t } = useTranslation('stock_transfer')

  // Warehouse name lookup so the From/To columns show "Main Warehouse - KL"
  // instead of "#1". The list endpoint only returns ids, so the lookup is
  // resolved client-side from a single /warehouses fetch.
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
      ...getTransferColumns(warehouseMap),
      {
        title: t('actions'),
        valueType: 'option' as const,
        fixed: 'right' as const,
        width: 120,
        render: (_: unknown, row: TransferRow) => [
          <a key="view" onClick={() => navigate(`/inventory/transfers/${row.id}`)}>
            {t('view', { defaultValue: 'View' })}
          </a>,
          ...(row.status === 'DRAFT'
            ? [
                <a
                  key="edit"
                  onClick={() => navigate(`/inventory/transfers/${row.id}/edit`)}
                >
                  {t('edit', { defaultValue: 'Edit' })}
                </a>,
              ]
            : []),
        ],
      },
    ],
    [warehouseMap, navigate, t],
  )

  return (
    <ResourceListPage<TransferRow>
      title={t('title')}
      columns={columns}
      fetchData={fetchTransfers}
      createPath="/inventory/transfers/new"
    />
  )
}
