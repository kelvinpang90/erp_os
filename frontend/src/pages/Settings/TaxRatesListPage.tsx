import type { ProColumns } from '@ant-design/pro-components'
import { Badge, Tag } from 'antd'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'

type TaxRateType = 'SST_SALES' | 'SST_SERVICE' | 'EXEMPT'

interface TaxRateRow {
  id: number
  code: string
  name: string
  rate: number | string
  type: TaxRateType
  is_active: boolean
}

const TYPE_COLORS: Record<TaxRateType, string> = {
  SST_SALES: 'blue',
  SST_SERVICE: 'cyan',
  EXEMPT: 'default',
}

async function fetchTaxRates(params: { current?: number; pageSize?: number }) {
  const { current = 1, pageSize = 20 } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  const res = await axiosInstance.get(`/tax-rates?${query}`)
  return res.data
}

export default function TaxRatesListPage() {
  const { t } = useTranslation('settings')

  const columns: ProColumns<TaxRateRow>[] = [
    { title: t('tax_rates.columns.code'), dataIndex: 'code', width: 120, fixed: 'left' },
    { title: t('tax_rates.columns.name'), dataIndex: 'name', ellipsis: true },
    {
      title: t('tax_rates.columns.rate'),
      dataIndex: 'rate',
      width: 100,
      hideInSearch: true,
      render: (val) => `${Number(val)}%`,
    },
    {
      title: t('tax_rates.columns.type'),
      dataIndex: 'type',
      width: 140,
      hideInSearch: true,
      render: (val) => <Tag color={TYPE_COLORS[val as TaxRateType] ?? 'default'}>{String(val)}</Tag>,
    },
    {
      title: t('tax_rates.columns.status'),
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
    <ResourceListPage<TaxRateRow>
      title={t('tax_rates.title')}
      columns={columns}
      fetchData={fetchTaxRates}
    />
  )
}
