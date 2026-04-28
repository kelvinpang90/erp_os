import { ScanOutlined } from '@ant-design/icons'
import { Button } from 'antd'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { poColumns, type PORow } from './POColumns'

async function fetchPOs(params: {
  current?: number
  pageSize?: number
  document_no?: string
  status?: string
}) {
  const { current = 1, pageSize = 20, document_no, status } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  if (document_no) query.set('search', document_no)
  if (status) query.set('status', status)
  const res = await axiosInstance.get(`/purchase-orders?${query}`)
  return res.data
}

export default function POListPage() {
  const navigate = useNavigate()
  const { t } = useTranslation('ocr')

  return (
    <ResourceListPage<PORow>
      title="Purchase Orders"
      columns={[
        ...poColumns,
        {
          title: 'Action',
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/purchase/orders/${row.id}`)}>
              View
            </a>,
            ...(row.status === 'DRAFT'
              ? [
                  <a key="edit" onClick={() => navigate(`/purchase/orders/${row.id}/edit`)}>
                    Edit
                  </a>,
                ]
              : []),
          ],
        },
      ]}
      fetchData={fetchPOs}
      createPath="/purchase/orders/create"
      toolbarActions={[
        <Button
          key="ocr-upload"
          icon={<ScanOutlined />}
          onClick={() => navigate('/purchase/orders/ocr-upload')}
        >
          {t('page_title')}
        </Button>,
      ]}
    />
  )
}
