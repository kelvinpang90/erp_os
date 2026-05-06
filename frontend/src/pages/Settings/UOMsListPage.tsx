import type { ProColumns } from '@ant-design/pro-components'
import { Badge } from 'antd'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'

interface UOMRow {
  id: number
  code: string
  name: string
  category?: string
  is_active: boolean
}

async function fetchUOMs(params: { current?: number; pageSize?: number }) {
  const { current = 1, pageSize = 20 } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  const res = await axiosInstance.get(`/uoms?${query}`)
  return res.data
}

export default function UOMsListPage() {
  const { t } = useTranslation('settings')

  const columns: ProColumns<UOMRow>[] = [
    { title: t('uoms.columns.code'), dataIndex: 'code', width: 120, fixed: 'left' },
    { title: t('uoms.columns.name'), dataIndex: 'name', ellipsis: true },
    {
      title: t('uoms.columns.category'),
      dataIndex: 'category',
      width: 140,
      hideInSearch: true,
      render: (val) => val || '—',
    },
    {
      title: t('uoms.columns.status'),
      dataIndex: 'is_active',
      width: 100,
      hideInSearch: true,
      render: (val) => (
        <Badge
          status={val ? 'success' : 'default'}
          text={val ? t('currencies.active') : t('currencies.inactive')}
        />
      ),
    },
  ]

  return (
    <ResourceListPage<UOMRow>
      title={t('uoms.title')}
      columns={columns}
      fetchData={fetchUOMs}
    />
  )
}
