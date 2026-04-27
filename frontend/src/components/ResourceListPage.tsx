import { PlusOutlined } from '@ant-design/icons'
import { ActionType, ProTable } from '@ant-design/pro-components'
import type { ProColumns } from '@ant-design/pro-components'
import { Button } from 'antd'
import { useRef } from 'react'
import { useNavigate } from 'react-router-dom'

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

interface ResourceListPageProps<T extends object> {
  title: string
  columns: ProColumns<T>[]
  fetchData: (params: {
    current?: number
    pageSize?: number
    [key: string]: unknown
  }) => Promise<PaginatedResponse<T>>
  createPath?: string
  rowKey?: string
  toolbarActions?: React.ReactNode[]
}

export default function ResourceListPage<T extends object>({
  title,
  columns,
  fetchData,
  createPath,
  rowKey = 'id',
  toolbarActions = [],
}: ResourceListPageProps<T>) {
  const navigate = useNavigate()
  const actionRef = useRef<ActionType>()

  return (
    <ProTable<T>
      actionRef={actionRef}
      rowKey={rowKey}
      headerTitle={title}
      columns={columns}
      request={async (params) => {
        const page = params.current ?? 1
        const pageSize = params.pageSize ?? 20
        const rest = { ...params }
        delete rest.current
        delete rest.pageSize

        const res = await fetchData({ ...rest, current: page, pageSize })
        return {
          data: res.items,
          total: res.total,
          success: true,
        }
      }}
      pagination={{
        defaultPageSize: 20,
        pageSizeOptions: ['20', '50', '100'],
        showSizeChanger: true,
      }}
      toolBarRender={() => [
        ...toolbarActions,
        createPath && (
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate(createPath)}
          >
            Create
          </Button>
        ),
      ]}
      search={{ labelWidth: 'auto' }}
    />
  )
}
