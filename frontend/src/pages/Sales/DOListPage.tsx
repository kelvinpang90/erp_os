import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { doColumns, type DORow } from './DOColumns'

async function fetchDOs(params: {
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
  const res = await axiosInstance.get(`/delivery-orders?${query}`)
  return res.data
}

export default function DOListPage() {
  const navigate = useNavigate()

  return (
    <ResourceListPage<DORow>
      title="Delivery Orders"
      columns={[
        ...doColumns,
        {
          title: 'Action',
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/sales/delivery/${row.id}`)}>
              View
            </a>,
            <a key="so" onClick={() => navigate(`/sales/orders/${row.sales_order_id}`)}>
              SO
            </a>,
          ],
        },
      ]}
      fetchData={fetchDOs}
      createPath="/sales/delivery/create"
    />
  )
}
