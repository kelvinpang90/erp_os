import type { ProColumns } from '@ant-design/pro-components'
import { Badge } from 'antd'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'

interface BrandRow {
  id: number
  code: string
  name: string
  country?: string
  is_active: boolean
}

async function fetchBrands(params: { current?: number; pageSize?: number }) {
  const { current = 1, pageSize = 20 } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  const res = await axiosInstance.get(`/brands?${query}`)
  return res.data
}

export default function BrandsListPage() {
  const { t } = useTranslation('settings')

  const columns: ProColumns<BrandRow>[] = [
    { title: t('brands.columns.code'), dataIndex: 'code', width: 120, fixed: 'left' },
    { title: t('brands.columns.name'), dataIndex: 'name', ellipsis: true },
    {
      title: t('brands.columns.country'),
      dataIndex: 'country',
      width: 120,
      hideInSearch: true,
      render: (val) => val || '—',
    },
    {
      title: t('brands.columns.status'),
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
    <ResourceListPage<BrandRow>
      title={t('brands.title')}
      columns={columns}
      fetchData={fetchBrands}
    />
  )
}
