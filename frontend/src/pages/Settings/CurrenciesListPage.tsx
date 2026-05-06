import type { ProColumns } from '@ant-design/pro-components'
import { Badge, Tag } from 'antd'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'

interface CurrencyRow {
  id: number
  code: string
  name: string
  symbol: string
  decimal_places: number
  is_base: boolean
  is_active: boolean
}

async function fetchCurrencies(params: { current?: number; pageSize?: number }) {
  const { current = 1, pageSize = 20 } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  const res = await axiosInstance.get(`/currencies?${query}`)
  return res.data
}

export default function CurrenciesListPage() {
  const { t } = useTranslation('settings')

  const columns: ProColumns<CurrencyRow>[] = [
    { title: t('currencies.columns.code'), dataIndex: 'code', width: 100, fixed: 'left' },
    { title: t('currencies.columns.name'), dataIndex: 'name', ellipsis: true },
    { title: t('currencies.columns.symbol'), dataIndex: 'symbol', width: 90, hideInSearch: true },
    {
      title: t('currencies.columns.decimal_places'),
      dataIndex: 'decimal_places',
      width: 100,
      hideInSearch: true,
    },
    {
      title: t('currencies.columns.is_base'),
      dataIndex: 'is_base',
      width: 90,
      hideInSearch: true,
      render: (val) => (val ? <Tag color="gold">★</Tag> : '—'),
    },
    {
      title: t('currencies.columns.status'),
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
    <ResourceListPage<CurrencyRow>
      title={t('currencies.title')}
      columns={columns}
      fetchData={fetchCurrencies}
    />
  )
}
