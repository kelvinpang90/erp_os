import { useRef } from 'react'
import { App, Popconfirm } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { ActionType } from '@ant-design/pro-components'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { buildWarehouseColumns, type WarehouseRow } from './WarehouseColumns'

async function fetchWarehouses(params: {
  current?: number
  pageSize?: number
  include_inactive?: string
}) {
  const { current = 1, pageSize = 20, include_inactive } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  if (include_inactive === 'true') query.set('include_inactive', 'true')
  const res = await axiosInstance.get(`/warehouses?${query}`)
  return res.data
}

export default function WarehouseListPage() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation('warehouse')
  const actionRef = useRef<ActionType>()

  const handleDelete = async (id: number) => {
    try {
      await axiosInstance.delete(`/warehouses/${id}`)
      message.success(t('delete_success'))
      actionRef.current?.reload()
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { error_code?: string; message?: string } } }
      if (apiErr?.response?.data?.error_code === 'WAREHOUSE_MAIN_DELETE_FORBIDDEN') {
        message.error(t('cannot_delete_main'))
      } else {
        message.error(apiErr?.response?.data?.message ?? t('delete_failed'))
      }
    }
  }

  return (
    <ResourceListPage<WarehouseRow>
      title={t('title')}
      actionRef={actionRef}
      columns={[
        ...buildWarehouseColumns(t),
        {
          title: t('include_inactive'),
          dataIndex: 'include_inactive',
          hideInTable: true,
          valueType: 'select',
          valueEnum: {
            true: { text: t('yes') },
          },
          fieldProps: { allowClear: true, placeholder: t('active_only') },
        },
        {
          title: t('action'),
          valueType: 'option',
          fixed: 'right',
          width: 160,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/settings/warehouses/${row.id}`)}>
              {t('view')}
            </a>,
            <a key="edit" onClick={() => navigate(`/settings/warehouses/${row.id}/edit`)}>
              {t('edit')}
            </a>,
            <Popconfirm
              key="delete"
              title={t('delete_confirm')}
              onConfirm={() => handleDelete(row.id)}
              okText={t('delete')}
              okButtonProps={{ danger: true }}
            >
              <a style={{ color: '#ff4d4f' }}>{t('delete')}</a>
            </Popconfirm>,
          ],
        },
      ]}
      fetchData={fetchWarehouses}
      createPath="/settings/warehouses/create"
    />
  )
}
