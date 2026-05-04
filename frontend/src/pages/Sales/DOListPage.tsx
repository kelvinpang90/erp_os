import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { getDoColumns, type DORow } from './DOColumns'

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
  const { t } = useTranslation(['delivery_order', 'common'])

  return (
    <ResourceListPage<DORow>
      title={t('delivery_order:title')}
      columns={[
        ...getDoColumns((key, opts) =>
          t(`delivery_order:${key}`, (opts ?? {}) as never) as unknown as string,
        ),
        {
          title: t('delivery_order:actions'),
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/sales/delivery/${row.id}`)}>
              {t('delivery_order:buttons.view')}
            </a>,
            <a key="so" onClick={() => navigate(`/sales/orders/${row.sales_order_id}`)}>
              {t('delivery_order:buttons.so')}
            </a>,
          ],
        },
      ]}
      fetchData={fetchDOs}
      createPath="/sales/delivery/create"
    />
  )
}
