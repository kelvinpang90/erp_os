import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { adjustmentColumns, type AdjustmentRow } from './adjustmentColumns'

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

  return (
    <ResourceListPage<AdjustmentRow>
      title={t('title')}
      columns={[
        ...adjustmentColumns,
        {
          title: t('actions'),
          valueType: 'option',
          fixed: 'right',
          width: 100,
          render: (_, row) => [
            <a
              key="view"
              onClick={() => navigate(`/inventory/adjustments/${row.id}`)}
            >
              {t('view', { defaultValue: 'View' })}
            </a>,
          ],
        },
      ]}
      fetchData={fetchAdjustments}
      createPath="/inventory/adjustments/new"
    />
  )
}
