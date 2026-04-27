import { useRef } from 'react'
import { App, Popconfirm } from 'antd'
import { useNavigate } from 'react-router-dom'
import type { ActionType } from '@ant-design/pro-components'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { warehouseColumns, type WarehouseRow } from './WarehouseColumns'

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
  const actionRef = useRef<ActionType>()

  const handleDelete = async (id: number) => {
    try {
      await axiosInstance.delete(`/warehouses/${id}`)
      message.success('Warehouse deleted')
      actionRef.current?.reload()
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { error_code?: string; message?: string } } }
      if (apiErr?.response?.data?.error_code === 'WAREHOUSE_MAIN_DELETE_FORBIDDEN') {
        message.error('Main warehouse cannot be deleted')
      } else {
        message.error(apiErr?.response?.data?.message ?? 'Delete failed')
      }
    }
  }

  return (
    <ResourceListPage<WarehouseRow>
      title="Warehouses"
      actionRef={actionRef}
      columns={[
        ...warehouseColumns,
        {
          title: 'Include Inactive',
          dataIndex: 'include_inactive',
          hideInTable: true,
          valueType: 'select',
          valueEnum: {
            true: { text: 'Yes' },
          },
          fieldProps: { allowClear: true, placeholder: 'Active only' },
        },
        {
          title: 'Action',
          valueType: 'option',
          fixed: 'right',
          width: 160,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/settings/warehouses/${row.id}`)}>
              View
            </a>,
            <a key="edit" onClick={() => navigate(`/settings/warehouses/${row.id}/edit`)}>
              Edit
            </a>,
            <Popconfirm
              key="delete"
              title="Delete this warehouse?"
              onConfirm={() => handleDelete(row.id)}
              okText="Delete"
              okButtonProps={{ danger: true }}
            >
              <a style={{ color: '#ff4d4f' }}>Delete</a>
            </Popconfirm>,
          ],
        },
      ]}
      fetchData={fetchWarehouses}
      createPath="/settings/warehouses/create"
    />
  )
}
