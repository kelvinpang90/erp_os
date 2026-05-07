import type { ProColumns } from '@ant-design/pro-components'
import { Badge } from 'antd'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'

interface CurrencyRow {
  code: string
  name: string
  symbol: string
  decimal_places: number
  is_active: boolean
  created_at: string
}

async function fetchCurrencies(params: { current?: number; pageSize?: number }) {
  const { current = 1, pageSize = 20 } = params
  // /api/currencies returns a flat array (no pagination), so wrap it
  // into the shape ResourceListPage expects.
  const res = await axiosInstance.get<CurrencyRow[]>(`/currencies`)
  const items = Array.isArray(res.data) ? res.data : []
  return {
    items,
    total: items.length,
    page: current,
    page_size: pageSize,
    total_pages: 1,
  }
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
      rowKey="code"
      columns={columns}
      fetchData={fetchCurrencies}
    />
  )
}
