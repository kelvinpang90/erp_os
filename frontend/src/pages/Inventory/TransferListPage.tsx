import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { transferColumns, type TransferRow } from './transferColumns'

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

  return (
    <ResourceListPage<TransferRow>
      title={t('title')}
      columns={[
        ...transferColumns,
        {
          title: t('actions'),
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
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
      ]}
      fetchData={fetchTransfers}
      createPath="/inventory/transfers/new"
    />
  )
}
