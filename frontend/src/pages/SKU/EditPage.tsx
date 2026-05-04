import {
  ProForm,
  ProFormDigit,
  ProFormSelect,
  ProFormSwitch,
  ProFormText,
  ProFormTextArea,
} from '@ant-design/pro-components'
import { App, Card, Skeleton } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

export default function SKUEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isCreate = !id
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation('sku')

  const COSTING_METHODS = useMemo(
    () => [
      { value: 'WEIGHTED_AVERAGE', label: t('costingMethod.weightedAverage') },
      { value: 'FIFO', label: t('costingMethod.fifo') },
      { value: 'SPECIFIC', label: t('costingMethod.specific') },
    ],
    [t],
  )

  const [initialValues, setInitialValues] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(!isCreate)
  const [uomOptions, setUomOptions] = useState<{ value: number; label: string }[]>([])
  const [taxRateOptions, setTaxRateOptions] = useState<{ value: number; label: string }[]>([])

  useEffect(() => {
    const loadOptions = async () => {
      const [uomsRes, taxRes] = await Promise.all([
        axiosInstance.get('/uoms?page_size=100&is_active=true'),
        axiosInstance.get('/tax-rates?page_size=100&is_active=true'),
      ])
      setUomOptions(uomsRes.data.items.map((u: { id: number; code: string; name: string }) => ({ value: u.id, label: `${u.code} - ${u.name}` })))
      setTaxRateOptions(taxRes.data.items.map((tr: { id: number; code: string; name: string; rate: string }) => ({ value: tr.id, label: `${tr.code} (${tr.rate}%)` })))
    }
    loadOptions().catch(console.error)
  }, [])

  useEffect(() => {
    if (!isCreate && id) {
      axiosInstance.get(`/skus/${id}`)
        .then((res) => setInitialValues(res.data))
        .catch(() => message.error(t('messages.loadFailed')))
        .finally(() => setLoading(false))
    }
  }, [id, isCreate, message, t])

  const handleSubmit = async (values: Record<string, unknown>) => {
    try {
      if (isCreate) {
        await axiosInstance.post('/skus', values)
        message.success(t('messages.created'))
      } else {
        await axiosInstance.patch(`/skus/${id}`, values)
        message.success(t('messages.updated'))
      }
      navigate('/skus')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? t('messages.operationFailed')
      message.error(msg)
    }
  }

  if (loading) return <Skeleton active />

  return (
    <Card title={isCreate ? t('create') : t('edit')}>
      <ProForm
        initialValues={initialValues ?? {}}
        onFinish={handleSubmit}
        onReset={() => navigate('/skus')}
      >
        <ProForm.Group>
          <ProFormText
            name="code"
            label={t('form.code')}
            rules={[]}
            fieldProps={{ maxLength: 64, placeholder: t('form.codePlaceholder') }}
            disabled={!isCreate}
            width="md"
          />
          <ProFormText name="barcode" label={t('form.barcode')} width="md" />
        </ProForm.Group>

        <ProForm.Group>
          <ProFormText
            name="name"
            label={t('form.nameEn')}
            rules={[{ required: true }]}
            width="lg"
          />
          <ProFormText name="name_zh" label={t('form.nameZh')} width="lg" />
        </ProForm.Group>

        <ProFormTextArea name="description" label={t('form.description')} fieldProps={{ rows: 2 }} />

        <ProForm.Group>
          <ProFormSelect
            name="base_uom_id"
            label={t('form.baseUom')}
            options={uomOptions}
            rules={[{ required: true }]}
            width="md"
          />
          <ProFormSelect
            name="tax_rate_id"
            label={t('form.taxRate')}
            options={taxRateOptions}
            rules={[{ required: true }]}
            width="md"
          />
          <ProFormSelect
            name="costing_method"
            label={t('form.costingMethod')}
            options={COSTING_METHODS}
            initialValue="WEIGHTED_AVERAGE"
            width="md"
          />
        </ProForm.Group>

        <ProForm.Group>
          <ProFormDigit
            name="unit_price_excl_tax"
            label={t('form.unitPriceExclTax')}
            min={0}
            fieldProps={{ precision: 4 }}
            width="md"
          />
          <ProFormDigit
            name="unit_price_incl_tax"
            label={t('form.unitPriceInclTax')}
            min={0}
            fieldProps={{ precision: 4 }}
            width="md"
          />
        </ProForm.Group>

        <ProForm.Group>
          <ProFormDigit name="safety_stock" label={t('form.safetyStock')} min={0} width="sm" />
          <ProFormDigit name="reorder_point" label={t('form.reorderPoint')} min={0} width="sm" />
          <ProFormDigit name="reorder_qty" label={t('form.reorderQty')} min={0} width="sm" />
        </ProForm.Group>

        <ProForm.Group>
          <ProFormSwitch name="track_batch" label={t('form.trackBatch')} />
          <ProFormSwitch name="track_expiry" label={t('form.trackExpiry')} />
          <ProFormSwitch name="track_serial" label={t('form.trackSerial')} />
          {!isCreate && <ProFormSwitch name="is_active" label={t('form.active')} />}
        </ProForm.Group>
      </ProForm>
    </Card>
  )
}
