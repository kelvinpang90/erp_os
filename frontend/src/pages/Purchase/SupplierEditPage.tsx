import {
  ProForm,
  ProFormDigit,
  ProFormSelect,
  ProFormSwitch,
  ProFormText,
  ProFormTextArea,
} from '@ant-design/pro-components'
import { App, Card, Skeleton } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'

const COUNTRY_OPTIONS = [
  { value: 'MY', label: 'Malaysia' },
  { value: 'SG', label: 'Singapore' },
  { value: 'CN', label: 'China' },
  { value: 'US', label: 'United States' },
  { value: 'GB', label: 'United Kingdom' },
]

const CURRENCY_OPTIONS = [
  { value: 'MYR', label: 'MYR – Malaysian Ringgit' },
  { value: 'SGD', label: 'SGD – Singapore Dollar' },
  { value: 'USD', label: 'USD – US Dollar' },
  { value: 'CNY', label: 'CNY – Chinese Yuan' },
]

export default function SupplierEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isCreate = !id
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation(['supplier', 'common'])

  const [initialValues, setInitialValues] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(!isCreate)

  useEffect(() => {
    if (!isCreate && id) {
      axiosInstance
        .get(`/suppliers/${id}`)
        .then((res) => setInitialValues(res.data))
        .catch(() => message.error(t('messages.loadFailed')))
        .finally(() => setLoading(false))
    }
  }, [id, isCreate, message, t])

  const handleSubmit = async (values: Record<string, unknown>) => {
    try {
      if (isCreate) {
        await axiosInstance.post('/suppliers', values)
        message.success(t('messages.createSuccess'))
      } else {
        await axiosInstance.patch(`/suppliers/${id}`, values)
        message.success(t('messages.updateSuccess'))
      }
      navigate('/purchase/suppliers')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? t('common:operationFailed')
      message.error(msg)
    }
  }

  if (loading) return <Skeleton active />

  return (
    <Card title={isCreate ? t('create') : t('edit')}>
      <ProForm
        initialValues={initialValues ?? { country: 'MY', currency: 'MYR', payment_terms_days: 30, credit_limit: 0 }}
        onFinish={handleSubmit}
        onReset={() => navigate('/purchase/suppliers')}
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
          <ProFormText name="name_zh" label={t('name_zh')} width="lg" />
        </ProForm.Group>

        <ProForm.Group title={t('sections.contact')}>
          <ProFormText name="contact_person" label={t('contact_person')} width="md" />
          <ProFormText name="email" label={t('email')} fieldProps={{ type: 'email' }} width="md" />
          <ProFormText name="phone" label={t('phone')} width="md" />
        </ProForm.Group>

        <ProForm.Group title={t('sections.businessRegistration')}>
          <ProFormText name="registration_no" label={t('registration_no')} width="md" />
          <ProFormText name="tin" label={t('tin')} width="sm" />
          <ProFormText name="sst_registration_no" label={t('sst_registration_no')} width="md" />
          <ProFormText name="msic_code" label={t('msic_code')} width="sm" />
        </ProForm.Group>

        <ProForm.Group title={t('address')}>
          <ProFormText name="address_line1" label={t('address_line1')} width="xl" />
          <ProFormText name="address_line2" label={t('address_line2')} width="xl" />
          <ProFormText name="city" label={t('city')} width="md" />
          <ProFormText name="state" label={t('state')} width="md" />
          <ProFormText name="postcode" label={t('postcode')} width="sm" />
          <ProFormSelect name="country" label={t('country')} options={COUNTRY_OPTIONS} width="md" />
        </ProForm.Group>

        <ProForm.Group title={t('sections.payment')}>
          <ProFormSelect name="currency" label={t('currency')} options={CURRENCY_OPTIONS} width="md" />
          <ProFormDigit name="payment_terms_days" label={t('payment_terms_days')} min={0} width="sm" />
          <ProFormDigit name="credit_limit" label={t('credit_limit')} min={0} fieldProps={{ precision: 2 }} width="md" />
        </ProForm.Group>

        <ProFormTextArea name="notes" label={t('notes')} fieldProps={{ rows: 2 }} />

        {!isCreate && <ProFormSwitch name="is_active" label={t('common:active')} />}
      </ProForm>
    </Card>
  )
}
