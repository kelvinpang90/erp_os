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

export default function CustomerEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isCreate = !id
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation('customer')

  const [initialValues, setInitialValues] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(!isCreate)
  const [customerType, setCustomerType] = useState<'B2B' | 'B2C'>('B2B')

  useEffect(() => {
    if (!isCreate && id) {
      axiosInstance
        .get(`/customers/${id}`)
        .then((res) => {
          setInitialValues(res.data)
          setCustomerType(res.data.customer_type ?? 'B2B')
        })
        .catch(() => message.error('Failed to load customer'))
        .finally(() => setLoading(false))
    }
  }, [id, isCreate, message])

  const handleSubmit = async (values: Record<string, unknown>) => {
    try {
      if (isCreate) {
        await axiosInstance.post('/customers', values)
        message.success('Customer created successfully')
      } else {
        await axiosInstance.patch(`/customers/${id}`, values)
        message.success('Customer updated successfully')
      }
      navigate('/sales/customers')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Operation failed'
      message.error(msg)
    }
  }

  if (loading) return <Skeleton active />

  return (
    <Card title={isCreate ? t('create') : t('edit')}>
      <ProForm
        initialValues={initialValues ?? { customer_type: 'B2B', country: 'MY', currency: 'MYR', payment_terms_days: 30, credit_limit: 0 }}
        onFinish={handleSubmit}
        onReset={() => navigate('/sales/customers')}
        onValuesChange={(changed) => {
          if (changed.customer_type) setCustomerType(changed.customer_type as 'B2B' | 'B2C')
        }}
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

        <ProForm.Group>
          <ProFormSelect
            name="customer_type"
            label={t('customer_type')}
            options={[
              { value: 'B2B', label: t('type_b2b') },
              { value: 'B2C', label: t('type_b2c') },
            ]}
            width="md"
          />
        </ProForm.Group>

        <ProForm.Group title="Contact">
          <ProFormText name="contact_person" label={t('contact_person')} width="md" />
          <ProFormText name="email" label={t('email')} fieldProps={{ type: 'email' }} width="md" />
          <ProFormText name="phone" label={t('phone')} width="md" />
        </ProForm.Group>

        {/* B2B 企业信息 — 仅当类型为 B2B 时显示 */}
        {customerType === 'B2B' && (
          <ProForm.Group title={t('business_info')}>
            <ProFormText name="registration_no" label={t('registration_no')} width="md" />
            <ProFormText name="tin" label={t('tin')} width="sm" />
            <ProFormText name="sst_registration_no" label={t('sst_registration_no')} width="md" />
            <ProFormText name="msic_code" label={t('msic_code')} width="sm" />
          </ProForm.Group>
        )}

        <ProForm.Group title="Address">
          <ProFormText name="address_line1" label={t('address_line1')} width="xl" />
          <ProFormText name="address_line2" label={t('address_line2')} width="xl" />
          <ProFormText name="city" label={t('city')} width="md" />
          <ProFormText name="state" label={t('state')} width="md" />
          <ProFormText name="postcode" label={t('postcode')} width="sm" />
          <ProFormSelect name="country" label={t('country')} options={COUNTRY_OPTIONS} width="md" />
        </ProForm.Group>

        <ProForm.Group title="Payment">
          <ProFormSelect name="currency" label={t('currency')} options={CURRENCY_OPTIONS} width="md" />
          <ProFormDigit name="payment_terms_days" label={t('payment_terms_days')} min={0} width="sm" />
          <ProFormDigit name="credit_limit" label={t('credit_limit')} min={0} fieldProps={{ precision: 2 }} width="md" />
        </ProForm.Group>

        <ProFormTextArea name="notes" label="Notes" fieldProps={{ rows: 2 }} />

        {!isCreate && <ProFormSwitch name="is_active" label="Active" />}
      </ProForm>
    </Card>
  )
}
