import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { getCustomerColumns, type CustomerRow } from './CustomerColumns'

async function fetchCustomers(params: {
  current?: number
  pageSize?: number
  code?: string
  name?: string
  customer_type?: string
  is_active?: string
}) {
  const { current = 1, pageSize = 20, code, name, customer_type, is_active } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  const search = code || name
  if (search) query.set('search', search)
  if (customer_type) query.set('customer_type', customer_type)
  if (is_active !== undefined) query.set('is_active', is_active)
  const res = await axiosInstance.get(`/customers?${query}`)
  return res.data
}

export default function CustomerListPage() {
  const navigate = useNavigate()
  const { t } = useTranslation(['customer', 'common'])

  return (
    <ResourceListPage<CustomerRow>
      title={t('customer:title')}
      columns={[
        ...getCustomerColumns(
          (key, opts) => t(`customer:${key}`, (opts ?? {}) as never) as unknown as string,
          (key, opts) => t(`common:${key}`, (opts ?? {}) as never) as unknown as string,
        ),
        {
          title: t('common:actions'),
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/sales/customers/${row.id}`)}>
              {t('customer:buttons.view')}
            </a>,
            <a key="edit" onClick={() => navigate(`/sales/customers/${row.id}/edit`)}>
              {t('common:edit')}
            </a>,
          ],
        },
      ]}
      fetchData={fetchCustomers}
      createPath="/sales/customers/create"
    />
  )
}
