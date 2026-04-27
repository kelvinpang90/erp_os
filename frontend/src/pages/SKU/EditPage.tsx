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
import { axiosInstance } from '../../api/client'

const COSTING_METHODS = [
  { value: 'WEIGHTED_AVERAGE', label: 'Weighted Average' },
  { value: 'FIFO', label: 'FIFO' },
  { value: 'SPECIFIC', label: 'Specific Identification' },
]

export default function SKUEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isCreate = !id
  const navigate = useNavigate()
  const { message } = App.useApp()

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
      setTaxRateOptions(taxRes.data.items.map((t: { id: number; code: string; name: string; rate: string }) => ({ value: t.id, label: `${t.code} (${t.rate}%)` })))
    }
    loadOptions().catch(console.error)
  }, [])

  useEffect(() => {
    if (!isCreate && id) {
      axiosInstance.get(`/skus/${id}`)
        .then((res) => setInitialValues(res.data))
        .catch(() => message.error('Failed to load SKU'))
        .finally(() => setLoading(false))
    }
  }, [id, isCreate, message])

  const handleSubmit = async (values: Record<string, unknown>) => {
    try {
      if (isCreate) {
        await axiosInstance.post('/skus', values)
        message.success('SKU created successfully')
      } else {
        await axiosInstance.patch(`/skus/${id}`, values)
        message.success('SKU updated successfully')
      }
      navigate('/skus')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Operation failed'
      message.error(msg)
    }
  }

  if (loading) return <Skeleton active />

  return (
    <Card title={isCreate ? 'Create SKU' : 'Edit SKU'}>
      <ProForm
        initialValues={initialValues ?? {}}
        onFinish={handleSubmit}
        onReset={() => navigate('/skus')}
      >
        <ProForm.Group>
          <ProFormText
            name="code"
            label="SKU Code"
            rules={[]}
            fieldProps={{ maxLength: 64, placeholder: 'Auto-generated if empty' }}
            disabled={!isCreate}
            width="md"
          />
          <ProFormText name="barcode" label="Barcode" width="md" />
        </ProForm.Group>

        <ProForm.Group>
          <ProFormText
            name="name"
            label="Name (EN)"
            rules={[{ required: true }]}
            width="lg"
          />
          <ProFormText name="name_zh" label="Name (ZH)" width="lg" />
        </ProForm.Group>

        <ProFormTextArea name="description" label="Description" fieldProps={{ rows: 2 }} />

        <ProForm.Group>
          <ProFormSelect
            name="base_uom_id"
            label="Base UOM"
            options={uomOptions}
            rules={[{ required: true }]}
            width="md"
          />
          <ProFormSelect
            name="tax_rate_id"
            label="Tax Rate"
            options={taxRateOptions}
            rules={[{ required: true }]}
            width="md"
          />
          <ProFormSelect
            name="costing_method"
            label="Costing Method"
            options={COSTING_METHODS}
            initialValue="WEIGHTED_AVERAGE"
            width="md"
          />
        </ProForm.Group>

        <ProForm.Group>
          <ProFormDigit
            name="unit_price_excl_tax"
            label="Unit Price (excl. tax)"
            min={0}
            fieldProps={{ precision: 4 }}
            width="md"
          />
          <ProFormDigit
            name="unit_price_incl_tax"
            label="Unit Price (incl. tax)"
            min={0}
            fieldProps={{ precision: 4 }}
            width="md"
          />
        </ProForm.Group>

        <ProForm.Group>
          <ProFormDigit name="safety_stock" label="Safety Stock" min={0} width="sm" />
          <ProFormDigit name="reorder_point" label="Reorder Point" min={0} width="sm" />
          <ProFormDigit name="reorder_qty" label="Reorder Qty" min={0} width="sm" />
        </ProForm.Group>

        <ProForm.Group>
          <ProFormSwitch name="track_batch" label="Track Batch" />
          <ProFormSwitch name="track_expiry" label="Track Expiry" />
          <ProFormSwitch name="track_serial" label="Track Serial" />
          {!isCreate && <ProFormSwitch name="is_active" label="Active" />}
        </ProForm.Group>
      </ProForm>
    </Card>
  )
}
