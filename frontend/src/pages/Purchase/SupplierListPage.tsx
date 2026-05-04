import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { getSupplierColumns, type SupplierRow } from './SupplierColumns'

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
  const { t } = useTranslation(['supplier', 'common'])

  return (
    <ResourceListPage<SupplierRow>
      title={t('supplier:title')}
      columns={[
        ...getSupplierColumns(
          (key, opts) => t(`supplier:${key}`, (opts ?? {}) as never) as unknown as string,
          (key, opts) => t(`common:${key}`, (opts ?? {}) as never) as unknown as string,
        ),
        {
          title: t('common:actions'),
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/purchase/suppliers/${row.id}`)}>
              {t('supplier:buttons.view')}
            </a>,
            <a key="edit" onClick={() => navigate(`/purchase/suppliers/${row.id}/edit`)}>
              {t('common:edit')}
            </a>,
          ],
        },
      ]}
      fetchData={fetchSuppliers}
      createPath="/purchase/suppliers/create"
    />
  )
}
