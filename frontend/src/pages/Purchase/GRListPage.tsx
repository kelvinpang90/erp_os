import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { getGrColumns, type GRRow } from './GRColumns'

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
  const { t } = useTranslation(['goods_receipt', 'common'])

  return (
    <ResourceListPage<GRRow>
      title={t('goods_receipt:title')}
      columns={[
        ...getGrColumns((key, opts) =>
          t(`goods_receipt:${key}`, (opts ?? {}) as never) as string,
        ),
        {
          title: t('goods_receipt:actions'),
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a
              key="view"
              onClick={() => navigate(`/purchase/goods-receipts/${row.id}`)}
            >
              {t('goods_receipt:buttons.view')}
            </a>,
            <a
              key="po"
              onClick={() => navigate(`/purchase/orders/${row.purchase_order_id}`)}
            >
              {t('goods_receipt:buttons.po')}
            </a>,
          ],
        },
      ]}
      fetchData={fetchGRs}
      createPath="/purchase/goods-receipts/create"
    />
  )
}
