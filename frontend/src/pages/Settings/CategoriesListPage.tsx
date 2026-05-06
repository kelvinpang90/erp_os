import type { ProColumns } from '@ant-design/pro-components'
import { Badge } from 'antd'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'

interface CategoryRow {
  id: number
  code: string
  name: string
  parent_id?: number | null
  parent_name?: string | null
  is_active: boolean
}

async function fetchCategories(params: { current?: number; pageSize?: number }) {
  const { current = 1, pageSize = 20 } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  const res = await axiosInstance.get(`/categories?${query}`)
  return res.data
}

export default function CategoriesListPage() {
  const { t } = useTranslation('settings')

  const columns: ProColumns<CategoryRow>[] = [
    { title: t('categories.columns.code'), dataIndex: 'code', width: 120, fixed: 'left' },
    { title: t('categories.columns.name'), dataIndex: 'name', ellipsis: true },
    {
      title: t('categories.columns.parent'),
      dataIndex: 'parent_name',
      width: 160,
      hideInSearch: true,
      render: (_, row) => row.parent_name || (row.parent_id ? `#${row.parent_id}` : '—'),
    },
    {
      title: t('categories.columns.status'),
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
    <ResourceListPage<CategoryRow>
      title={t('categories.title')}
      columns={columns}
      fetchData={fetchCategories}
    />
  )
}
