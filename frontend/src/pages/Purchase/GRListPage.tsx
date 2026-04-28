import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { grColumns, type GRRow } from './GRColumns'

async function fetchGRs(params: {
  current?: number
  pageSize?: number
  document_no?: string
}) {
  const { current = 1, pageSize = 20, document_no } = params
  const query = new URLSearchParams({
    page: String(current),
    page_size: String(pageSize),
  })
  if (document_no) query.set('search', document_no)
  const res = await axiosInstance.get(`/goods-receipts?${query}`)
  return res.data
}

export default function GRListPage() {
  const navigate = useNavigate()
  const { t } = useTranslation('goods_receipt')

  return (
    <ResourceListPage<GRRow>
      title={t('title')}
      columns={[
        ...grColumns,
        {
          title: t('actions'),
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a
              key="view"
              onClick={() => navigate(`/purchase/goods-receipts/${row.id}`)}
            >
              View
            </a>,
            <a
              key="po"
              onClick={() => navigate(`/purchase/orders/${row.purchase_order_id}`)}
            >
              PO
            </a>,
          ],
        },
      ]}
      fetchData={fetchGRs}
      createPath="/purchase/goods-receipts/create"
    />
  )
}
