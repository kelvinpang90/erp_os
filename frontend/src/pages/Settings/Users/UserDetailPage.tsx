import { ArrowLeftOutlined, EditOutlined, KeyOutlined } from '@ant-design/icons'
import { ProDescriptions } from '@ant-design/pro-components'
import {
  App,
  Badge,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Space,
  Spin,
  Tag,
} from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../../api/client'

const ROLE_COLORS: Record<string, string> = {
  ADMIN: 'red',
  MANAGER: 'gold',
  SALES: 'blue',
  PURCHASER: 'green',
}

interface UserDetail {
  id: number
  email: string
  full_name: string
  locale?: string
  theme?: string
  is_active: boolean
  last_login_at?: string | null
  role_codes: string[]
  created_at?: string
  updated_at?: string
}

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation('users')
  const { message } = App.useApp()
  const [user, setUser] = useState<UserDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [resetOpen, setResetOpen] = useState(false)
  const [resetSubmitting, setResetSubmitting] = useState(false)
  const [form] = Form.useForm<{ new_password: string }>()

  useEffect(() => {
    if (!id) return
    axiosInstance
      .get(`/users/${id}`)
      .then((res) => setUser(res.data))
      .catch(() => navigate('/settings/users'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  const handleResetSubmit = async () => {
    try {
      const values = await form.validateFields()
      setResetSubmitting(true)
      await axiosInstance.post(`/users/${id}/reset-password`, {
        new_password: values.new_password,
      })
      message.success(t('reset_password_success'))
      setResetOpen(false)
      form.resetFields()
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { message?: string } } }
      if (apiErr?.response) {
        message.error(apiErr.response.data?.message ?? t('reset_password_failed'))
      }
    } finally {
      setResetSubmitting(false)
    }
  }

  if (loading)
    return (
      <Spin
        size="large"
        style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }}
      />
    )
  if (!user) return null

  return (
    <>
      <Card
        title={
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              type="text"
              onClick={() => navigate('/settings/users')}
            />
            {user.full_name} — {user.email}
          </Space>
        }
        extra={
          <Space>
            <Button icon={<KeyOutlined />} onClick={() => setResetOpen(true)}>
              {t('reset_password')}
            </Button>
            <Button
              icon={<EditOutlined />}
              onClick={() => navigate(`/settings/users/${id}/edit`)}
            >
              {t('edit')}
            </Button>
          </Space>
        }
      >
        <ProDescriptions column={2}>
          <ProDescriptions.Item label={t('columns.email')}>{user.email}</ProDescriptions.Item>
          <ProDescriptions.Item label={t('columns.full_name')}>
            {user.full_name}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('columns.status')}>
            <Badge
              status={user.is_active ? 'success' : 'default'}
              text={user.is_active ? t('active') : t('inactive')}
            />
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('columns.last_login')}>
            {user.last_login_at
              ? dayjs(user.last_login_at).format('YYYY-MM-DD HH:mm')
              : t('never')}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('form.locale')}>
            {user.locale || '—'}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('form.theme')}>
            {user.theme || '—'}
          </ProDescriptions.Item>
          <ProDescriptions.Item label={t('columns.roles')} span={2}>
            {user.role_codes?.length
              ? user.role_codes.map((code) => (
                  <Tag
                    key={code}
                    color={ROLE_COLORS[code] ?? 'default'}
                    style={{ marginInlineEnd: 4 }}
                  >
                    {code}
                  </Tag>
                ))
              : '—'}
          </ProDescriptions.Item>
        </ProDescriptions>
      </Card>

      <Modal
        title={t('reset_password')}
        open={resetOpen}
        onCancel={() => {
          setResetOpen(false)
          form.resetFields()
        }}
        onOk={handleResetSubmit}
        confirmLoading={resetSubmitting}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="new_password"
            label={t('new_password')}
            rules={[{ required: true, min: 8 }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
