import {
  ProForm,
  ProFormSelect,
  ProFormSwitch,
  ProFormText,
} from '@ant-design/pro-components'
import { App, Card, Skeleton } from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../../api/client'

const ROLE_OPTIONS = [
  { value: 'ADMIN', label: 'ADMIN' },
  { value: 'MANAGER', label: 'MANAGER' },
  { value: 'SALES', label: 'SALES' },
  { value: 'PURCHASER', label: 'PURCHASER' },
]

const LOCALE_OPTIONS = [
  { value: 'en-US', label: 'English (US)' },
  { value: 'zh-CN', label: '中文（简体）' },
]

const THEME_OPTIONS = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]

interface UserFormValues {
  email?: string
  full_name?: string
  password?: string
  role_codes?: string[]
  locale?: string
  theme?: string
  is_active?: boolean
}

export default function UserEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isCreate = !id
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation('users')

  const [initialValues, setInitialValues] = useState<UserFormValues | null>(null)
  const [loading, setLoading] = useState(!isCreate)

  useEffect(() => {
    if (!isCreate && id) {
      axiosInstance
        .get(`/users/${id}`)
        .then((res) => {
          const data = res.data
          setInitialValues({
            email: data.email,
            full_name: data.full_name,
            role_codes: data.role_codes ?? [],
            locale: data.locale,
            theme: data.theme,
            is_active: data.is_active,
          })
        })
        .catch(() => message.error(t('load_failed')))
        .finally(() => setLoading(false))
    }
  }, [id, isCreate, message, t])

  const handleSubmit = async (values: UserFormValues) => {
    try {
      if (isCreate) {
        await axiosInstance.post('/users', {
          email: values.email,
          full_name: values.full_name,
          password: values.password,
          role_codes: values.role_codes ?? [],
          locale: values.locale,
          theme: values.theme,
        })
        message.success(t('create_success'))
      } else {
        await axiosInstance.patch(`/users/${id}`, {
          full_name: values.full_name,
          role_codes: values.role_codes,
          locale: values.locale,
          theme: values.theme,
          is_active: values.is_active,
        })
        message.success(t('update_success'))
      }
      navigate('/settings/users')
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { error_code?: string; message?: string } } }
      const code = apiErr?.response?.data?.error_code
      if (code === 'CANNOT_DEACTIVATE_SELF') {
        message.error(t('cannot_deactivate_self'))
      } else {
        message.error(apiErr?.response?.data?.message ?? t('operation_failed'))
      }
    }
  }

  if (loading) return <Skeleton active />

  return (
    <Card title={isCreate ? t('create') : t('edit')}>
      <ProForm<UserFormValues>
        initialValues={initialValues ?? { role_codes: [], locale: 'en-US', theme: 'light', is_active: true }}
        onFinish={handleSubmit}
        onReset={() => navigate('/settings/users')}
      >
        <ProForm.Group>
          <ProFormText
            name="email"
            label={t('form.email')}
            rules={[{ required: true, type: 'email' }]}
            disabled={!isCreate}
            width="md"
          />
          <ProFormText
            name="full_name"
            label={t('form.full_name')}
            rules={[{ required: true }]}
            width="md"
          />
        </ProForm.Group>

        {isCreate && (
          <ProForm.Group>
            <ProFormText.Password
              name="password"
              label={t('form.password')}
              rules={[{ required: true, min: 8 }]}
              width="md"
            />
          </ProForm.Group>
        )}

        <ProForm.Group>
          <ProFormSelect
            name="role_codes"
            label={t('form.roles')}
            mode="multiple"
            options={ROLE_OPTIONS}
            rules={[{ required: true }]}
            width="lg"
          />
        </ProForm.Group>

        <ProForm.Group>
          <ProFormSelect name="locale" label={t('form.locale')} options={LOCALE_OPTIONS} width="sm" />
          <ProFormSelect name="theme" label={t('form.theme')} options={THEME_OPTIONS} width="sm" />
        </ProForm.Group>

        {!isCreate && <ProFormSwitch name="is_active" label={t('form.is_active')} />}
      </ProForm>
    </Card>
  )
}
