import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { getSoColumns, type SORow } from './SOColumns'

async function fetchSOs(params: {
  current?: number
  pageSize?: number
  document_no?: string
  status?: string
}) {
  const { current = 1, pageSize = 20, document_no, status } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  if (document_no) query.set('search', document_no)
  if (status) query.set('status', status)
  const res = await axiosInstance.get(`/sales-orders?${query}`)
  return res.data
}

export default function SOListPage() {
  const navigate = useNavigate()
  const { t } = useTranslation(['sales_order', 'common'])

  return (
    <ResourceListPage<SORow>
      title={t('sales_order:title')}
      columns={[
        ...getSoColumns((key, opts) =>
          t(`sales_order:${key}`, (opts ?? {}) as never) as unknown as string,
        ),
        {
          title: t('sales_order:actions'),
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/sales/orders/${row.id}`)}>
              {t('sales_order:buttons.view')}
            </a>,
            ...(row.status === 'DRAFT'
              ? [
                  <a key="edit" onClick={() => navigate(`/sales/orders/${row.id}/edit`)}>
                    {t('common:edit')}
                  </a>,
                ]
              : []),
          ],
        },
      ]}
      fetchData={fetchSOs}
      createPath="/sales/orders/create"
    />
  )
}
