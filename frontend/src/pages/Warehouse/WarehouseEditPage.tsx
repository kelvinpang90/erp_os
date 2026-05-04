import {
  ProForm,
  ProFormSelect,
  ProFormSwitch,
  ProFormText,
} from '@ant-design/pro-components'
import { App, Card, Skeleton } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'

const COUNTRY_OPTIONS = [
  { value: 'MY', label: 'Malaysia' },
  { value: 'SG', label: 'Singapore' },
]

export default function WarehouseEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isCreate = !id
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation('warehouse')

  const WAREHOUSE_TYPE_OPTIONS = useMemo(
    () => [
      { value: 'MAIN', label: t('type_label.MAIN') },
      { value: 'BRANCH', label: t('type_label.BRANCH') },
      { value: 'TRANSIT', label: t('type_label.TRANSIT') },
      { value: 'QUARANTINE', label: t('type_label.QUARANTINE') },
    ],
    [t],
  )

  const [initialValues, setInitialValues] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(!isCreate)
  const [userOptions, setUserOptions] = useState<{ value: number; label: string }[]>([])

  useEffect(() => {
    axiosInstance
      .get('/auth/me')
      .then((res) => {
        const orgId = res.data?.organization?.id
        if (orgId) {
          return axiosInstance.get(`/auth/users?page_size=100`)
        }
      })
      .then((res) => {
        if (res?.data?.items) {
          setUserOptions(
            res.data.items.map((u: { id: number; full_name: string; email: string }) => ({
              value: u.id,
              label: `${u.full_name} (${u.email})`,
            }))
          )
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!isCreate && id) {
      axiosInstance
        .get(`/warehouses/${id}`)
        .then((res) => setInitialValues(res.data))
        .catch(() => message.error(t('load_failed')))
        .finally(() => setLoading(false))
    }
  }, [id, isCreate, message, t])

  const handleSubmit = async (values: Record<string, unknown>) => {
    try {
      if (isCreate) {
        await axiosInstance.post('/warehouses', values)
        message.success(t('create_success'))
      } else {
        await axiosInstance.patch(`/warehouses/${id}`, values)
        message.success(t('update_success'))
      }
      navigate('/settings/warehouses')
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { message?: string; error_code?: string } } }
      const errCode = apiErr?.response?.data?.error_code
      if (errCode === 'WAREHOUSE_MAIN_DELETE_FORBIDDEN') {
        message.error(t('cannot_delete_main'))
      } else {
        message.error(apiErr?.response?.data?.message ?? t('operation_failed'))
      }
    }
  }

  if (loading) return <Skeleton active />

  return (
    <Card title={isCreate ? t('create') : t('edit')}>
      <ProForm
        initialValues={initialValues ?? { type: 'BRANCH', country: 'MY' }}
        onFinish={handleSubmit}
        onReset={() => navigate('/settings/warehouses')}
      >
        <ProForm.Group>
          <ProFormText
            name="code"
            label={t('code')}
            rules={[{ required: true }]}
            fieldProps={{ maxLength: 32 }}
            disabled={!isCreate}
            width="md"
          />
          <ProFormText name="name" label={t('name')} rules={[{ required: true }]} width="lg" />
          <ProFormSelect
            name="type"
            label={t('type')}
            options={WAREHOUSE_TYPE_OPTIONS}
            width="md"
          />
        </ProForm.Group>

        <ProForm.Group title={t('address_section')}>
          <ProFormText name="address_line1" label={t('address_line1')} width="xl" />
          <ProFormText name="address_line2" label={t('address_line2')} width="xl" />
          <ProFormText name="city" label={t('city')} width="md" />
          <ProFormText name="state" label={t('state')} width="md" />
          <ProFormText name="postcode" label={t('postcode')} width="sm" />
          <ProFormSelect name="country" label={t('country')} options={COUNTRY_OPTIONS} width="md" />
        </ProForm.Group>

        <ProForm.Group>
          <ProFormText name="phone" label={t('phone')} width="md" />
          <ProFormSelect
            name="manager_user_id"
            label={t('manager_user_id')}
            options={userOptions}
            fieldProps={{ placeholder: t('select_manager_placeholder'), allowClear: true }}
            width="md"
          />
        </ProForm.Group>

        {!isCreate && <ProFormSwitch name="is_active" label={t('active')} />}
      </ProForm>
    </Card>
  )
}
