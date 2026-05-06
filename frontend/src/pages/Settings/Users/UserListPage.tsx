import type { ActionType } from '@ant-design/pro-components'
import { App, Popconfirm } from 'antd'
import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../../api/client'
import ResourceListPage from '../../../components/ResourceListPage'
import { useAuthStore } from '../../../stores/authStore'
import { buildUserColumns, type UserRow } from './UserColumns'


async function fetchUsers(params: { current?: number; pageSize?: number }) {
  const { current = 1, pageSize = 20 } = params
  const query = new URLSearchParams({ page: String(current), page_size: String(pageSize) })
  const res = await axiosInstance.get(`/users?${query}`)
  return res.data
}

export default function UserListPage() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation('users')
  const { t: tc } = useTranslation('common')
  const actionRef = useRef<ActionType>()
  const currentUserId = useAuthStore((s) => s.user?.id)

  const handleDelete = async (id: number) => {
    try {
      await axiosInstance.delete(`/users/${id}`)
      message.success(t('delete_success'))
      actionRef.current?.reload()
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { error_code?: string; message?: string } } }
      const code = apiErr?.response?.data?.error_code
      if (code === 'CANNOT_DELETE_SELF') {
        message.error(t('cannot_delete_self'))
      } else {
        message.error(apiErr?.response?.data?.message ?? t('delete_failed'))
      }
    }
  }

  return (
    <ResourceListPage<UserRow>
      title={t('title')}
      actionRef={actionRef}
      columns={[
        ...buildUserColumns(t),
        {
          title: tc('actions'),
          dataIndex: 'action',
          valueType: 'option',
          fixed: 'right',
          width: 180,
          render: (_, row) => [
            <a key="view" onClick={() => navigate(`/settings/users/${row.id}`)}>
              {t('view')}
            </a>,
            <a key="edit" onClick={() => navigate(`/settings/users/${row.id}/edit`)}>
              {t('edit')}
            </a>,
            row.id !== currentUserId ? (
              <Popconfirm
                key="delete"
                title={t('delete_confirm')}
                onConfirm={() => handleDelete(row.id)}
                okButtonProps={{ danger: true }}
              >
                <a style={{ color: '#ff4d4f' }}>{tc('delete')}</a>
              </Popconfirm>
            ) : null,
          ],
        },
      ]}
      fetchData={fetchUsers}
      createPath="/settings/users/create"
    />
  )
}
