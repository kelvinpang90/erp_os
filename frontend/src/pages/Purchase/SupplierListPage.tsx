import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { supplierColumns, type SupplierRow } from './SupplierColumns'

async function fetchSuppliers(params: {
  current?: number
  pageSize?: number
  code?: string
  name?: string
  is_active?: string
}) {
  const { current = 1, pageSize = 20, code, name, is_active } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  const search = code || name
  if (search) query.set('search', search)
  if (is_active !== undefined) query.set('is_active', is_active)
  const res = await axiosInstance.get(`/suppliers?${query}`)
  return res.data
}

export default function SupplierListPage() {
  const navigate = useNavigate()

  return (
    <ResourceListPage<SupplierRow>
      title="Suppliers"
      columns={[
        ...supplierColumns,
        {
          title: 'Action',
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/purchase/suppliers/${row.id}`)}>
              View
            </a>,
            <a key="edit" onClick={() => navigate(`/purchase/suppliers/${row.id}/edit`)}>
              Edit
            </a>,
          ],
        },
      ]}
      fetchData={fetchSuppliers}
      createPath="/purchase/suppliers/create"
    />
  )
}
