import { useNavigate } from 'react-router-dom'
import ResourceListPage from '../../components/ResourceListPage'
import { axiosInstance } from '../../api/client'
import { skuColumns, type SKURow } from './columns'

async function fetchSKUs(params: {
  current?: number
  pageSize?: number
  code?: string
  name?: string
  is_active?: string
}) {
  const { current = 1, pageSize = 20, ...rest } = params
  const query = new URLSearchParams({
    page: String(current),
    page_size: String(pageSize),
    ...(rest.code ? { search: rest.code } : {}),
    ...(rest.name ? { search: rest.name } : {}),
    ...(rest.is_active !== undefined ? { is_active: rest.is_active } : {}),
  })
  const res = await axiosInstance.get(`/skus?${query}`)
  return res.data
}

export default function SKUListPage() {
  const navigate = useNavigate()

  return (
    <ResourceListPage<SKURow>
      title="SKU Management"
      columns={[
        ...skuColumns,
        {
          title: 'Action',
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/skus/${row.id}`)}>
              View
            </a>,
            <a key="edit" onClick={() => navigate(`/skus/${row.id}/edit`)}>
              Edit
            </a>,
          ],
        },
      ]}
      fetchData={fetchSKUs}
      createPath="/skus/create"
    />
  )
}
