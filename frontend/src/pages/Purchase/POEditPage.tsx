import {
  EditableProTable,
  ProForm,
  ProFormDatePicker,
  ProFormDigit,
  ProFormSelect,
  ProFormTextArea,
  type ProColumns,
} from '@ant-design/pro-components'
import { App, Card, Row, Skeleton, Space, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface LineRow {
  id: string | number
  sku_id?: number
  uom_id?: number
  description?: string
  qty_ordered?: number
  unit_price_excl_tax?: number
  tax_rate_id?: number
  tax_rate_percent?: number
  discount_percent?: number
}

const CURRENCY_OPTIONS = [
  { value: 'MYR', label: 'MYR' },
  { value: 'SGD', label: 'SGD' },
  { value: 'USD', label: 'USD' },
  { value: 'CNY', label: 'CNY' },
]

export default function POEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isCreate = !id
  const navigate = useNavigate()
  const { message } = App.useApp()

  const [initialValues, setInitialValues] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(!isCreate)
  const [lines, setLines] = useState<LineRow[]>([{ id: `new-${Date.now()}` }])
  const [editableKeys, setEditableKeys] = useState<(string | number)[]>([])

  const [supplierOptions, setSupplierOptions] = useState<{ value: number; label: string }[]>([])
  const [warehouseOptions, setWarehouseOptions] = useState<{ value: number; label: string }[]>([])
  const [skuOptions, setSkuOptions] = useState<{ value: number; label: string }[]>([])
  const [skuLoading, setSkuLoading] = useState(false)
  const [uomOptions, setUomOptions] = useState<{ value: number; label: string }[]>([])
  const [taxRateOptions, setTaxRateOptions] = useState<{ value: number; label: string; rate: number }[]>([])

  // ── SKU server-side search with debounce ──────────────────────────────────
  const skuDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchSkus = useCallback((keyword: string) => {
    setSkuLoading(true)
    const q = keyword ? `&search=${encodeURIComponent(keyword)}` : ''
    axiosInstance
      .get(`/skus?page_size=50${q}`)
      .then((res) => {
        setSkuOptions(
          res.data.items.map((s: { id: number; code: string; name: string }) => ({
            value: s.id,
            label: `${s.code} — ${s.name}`,
          }))
        )
      })
      .catch(() => {/* silently ignore SKU search errors */})
      .finally(() => setSkuLoading(false))
  }, [])

  const handleSkuSearch = useCallback(
    (keyword: string) => {
      if (skuDebounceRef.current) clearTimeout(skuDebounceRef.current)
      skuDebounceRef.current = setTimeout(() => fetchSkus(keyword), 300)
    },
    [fetchSkus]
  )

  // ── Load reference data on mount ─────────────────────────────────────────
  useEffect(() => {
    // SKU: load first 50 immediately so the dropdown isn't empty on open
    fetchSkus('')

    // Small reference lists: use Promise.allSettled so one failure doesn't block others
    Promise.allSettled([
      axiosInstance.get('/suppliers?page_size=50'),
      axiosInstance.get('/warehouses?page_size=50'),
      axiosInstance.get('/uoms?page_size=100'),
      axiosInstance.get('/tax-rates?page_size=50'),
    ]).then(([sup, wh, uom, tax]) => {
      let anyFailed = false

      if (sup.status === 'fulfilled') {
        setSupplierOptions(
          sup.value.data.items.map((s: { id: number; name: string }) => ({ value: s.id, label: s.name }))
        )
      } else { anyFailed = true }

      if (wh.status === 'fulfilled') {
        setWarehouseOptions(
          wh.value.data.items.map((w: { id: number; name: string }) => ({ value: w.id, label: w.name }))
        )
      } else { anyFailed = true }

      if (uom.status === 'fulfilled') {
        setUomOptions(
          uom.value.data.items.map((u: { id: number; code: string }) => ({ value: u.id, label: u.code }))
        )
      } else { anyFailed = true }

      if (tax.status === 'fulfilled') {
        setTaxRateOptions(
          tax.value.data.items.map((t: { id: number; name: string; rate: string }) => ({
            value: t.id,
            label: `${t.name} (${t.rate}%)`,
            rate: parseFloat(t.rate),
          }))
        )
      } else { anyFailed = true }

      if (anyFailed) {
        message.warning('Some reference data failed to load. Please refresh if dropdowns are empty.')
      }
    })

    if (!isCreate && id) {
      axiosInstance
        .get(`/purchase-orders/${id}`)
        .then((res) => {
          const po = res.data
          setInitialValues({
            supplier_id: po.supplier_id,
            warehouse_id: po.warehouse_id,
            business_date: po.business_date,
            expected_date: po.expected_date,
            currency: po.currency,
            exchange_rate: parseFloat(po.exchange_rate),
            payment_terms_days: po.payment_terms_days,
            remarks: po.remarks,
          })
          const loadedLines: LineRow[] = po.lines.map((l: {
            id: number; sku_id: number; uom_id: number; description?: string
            qty_ordered: string; unit_price_excl_tax: string; tax_rate_id: number
            tax_rate_percent: string; discount_percent: string
          }) => ({
            id: l.id,
            sku_id: l.sku_id,
            uom_id: l.uom_id,
            description: l.description,
            qty_ordered: parseFloat(l.qty_ordered),
            unit_price_excl_tax: parseFloat(l.unit_price_excl_tax),
            tax_rate_id: l.tax_rate_id,
            tax_rate_percent: parseFloat(l.tax_rate_percent),
            discount_percent: parseFloat(l.discount_percent),
          }))
          setLines(loadedLines)
        })
        .catch(() => message.error('Failed to load purchase order'))
        .finally(() => setLoading(false))
    }
  }, [id, isCreate, message, fetchSkus])

  const lineColumns: ProColumns<LineRow>[] = [
    {
      title: 'SKU',
      dataIndex: 'sku_id',
      valueType: 'select',
      fieldProps: {
        options: skuOptions,
        showSearch: true,
        filterOption: false,          // let server handle filtering
        onSearch: handleSkuSearch,
        loading: skuLoading,
        notFoundContent: skuLoading ? 'Searching…' : 'No SKU found',
      },
      formItemProps: { rules: [{ required: true }] },
      width: 240,
    },
    {
      title: 'UOM',
      dataIndex: 'uom_id',
      valueType: 'select',
      fieldProps: { options: uomOptions },
      formItemProps: { rules: [{ required: true }] },
      width: 90,
    },
    {
      title: 'Qty',
      dataIndex: 'qty_ordered',
      valueType: 'digit',
      fieldProps: { min: 0.0001, precision: 4 },
      formItemProps: { rules: [{ required: true }] },
      width: 100,
    },
    {
      title: 'Unit Price',
      dataIndex: 'unit_price_excl_tax',
      valueType: 'digit',
      fieldProps: { min: 0, precision: 4 },
      formItemProps: { rules: [{ required: true }] },
      width: 120,
    },
    {
      title: 'Tax Rate',
      dataIndex: 'tax_rate_id',
      valueType: 'select',
      fieldProps: { options: taxRateOptions },
      formItemProps: { rules: [{ required: true }] },
      width: 140,
    },
    {
      title: 'Disc %',
      dataIndex: 'discount_percent',
      valueType: 'digit',
      fieldProps: { min: 0, max: 100, precision: 2 },
      width: 90,
    },
    {
      title: 'Description',
      dataIndex: 'description',
      width: 180,
    },
    {
      title: '',
      valueType: 'option',
      width: 60,
    },
  ]

  const totals = useMemo(() => {
    let subtotal = 0
    let tax = 0
    for (const l of lines) {
      const qty = l.qty_ordered ?? 0
      const price = l.unit_price_excl_tax ?? 0
      const disc = l.discount_percent ?? 0
      const taxPct = l.tax_rate_percent ?? (taxRateOptions.find((t) => t.value === l.tax_rate_id)?.rate ?? 0)
      const gross = qty * price
      const discAmt = gross * (disc / 100)
      const excl = gross - discAmt
      const taxAmt = excl * (taxPct / 100)
      subtotal += excl
      tax += taxAmt
    }
    return { subtotal, tax, total: subtotal + tax }
  }, [lines, taxRateOptions])

  const handleSubmit = async (values: Record<string, unknown>) => {
    const payload = {
      ...values,
      lines: lines.map((l) => ({
        sku_id: l.sku_id,
        uom_id: l.uom_id,
        description: l.description,
        qty_ordered: l.qty_ordered,
        unit_price_excl_tax: l.unit_price_excl_tax,
        tax_rate_id: l.tax_rate_id,
        tax_rate_percent: l.tax_rate_percent ?? taxRateOptions.find((t) => t.value === l.tax_rate_id)?.rate ?? 0,
        discount_percent: l.discount_percent ?? 0,
      })),
    }
    try {
      if (isCreate) {
        await axiosInstance.post('/purchase-orders', payload)
        message.success('Purchase order created.')
      } else {
        await axiosInstance.patch(`/purchase-orders/${id}`, payload)
        message.success('Purchase order updated.')
      }
      navigate('/purchase/orders')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Operation failed'
      message.error(msg)
    }
  }

  if (loading) return <Skeleton active />

  return (
    <Card title={isCreate ? 'New Purchase Order' : 'Edit Purchase Order'}>
      <ProForm
        initialValues={initialValues ?? {
          currency: 'MYR',
          exchange_rate: 1,
          payment_terms_days: 30,
        }}
        onFinish={handleSubmit}
        onReset={() => navigate('/purchase/orders')}
      >
        <ProForm.Group title="Order Details">
          <ProFormSelect
            name="supplier_id"
            label="Supplier"
            options={supplierOptions}
            rules={[{ required: true }]}
            fieldProps={{ showSearch: true }}
            width="lg"
          />
          <ProFormSelect
            name="warehouse_id"
            label="Warehouse"
            options={warehouseOptions}
            rules={[{ required: true }]}
            width="md"
          />
          <ProFormDatePicker name="business_date" label="Order Date" rules={[{ required: true }]} width="md" />
          <ProFormDatePicker name="expected_date" label="Expected Date" width="md" />
        </ProForm.Group>

        <ProForm.Group title="Payment">
          <ProFormSelect name="currency" label="Currency" options={CURRENCY_OPTIONS} width="sm" />
          <ProFormDigit name="exchange_rate" label="Exchange Rate" min={0.000001} fieldProps={{ precision: 8 }} width="sm" />
          <ProFormDigit name="payment_terms_days" label="Payment Terms (Days)" min={0} width="sm" />
        </ProForm.Group>

        <ProFormTextArea name="remarks" label="Remarks" fieldProps={{ rows: 2 }} />

        <Card title="Order Lines" size="small" style={{ marginBottom: 24 }}>
          <EditableProTable<LineRow>
            rowKey="id"
            value={lines}
            onChange={(v) => setLines(v as LineRow[])}
            columns={lineColumns}
            editable={{
              type: 'multiple',
              editableKeys,
              onChange: (keys) => setEditableKeys(keys as (string | number)[]),
              actionRender: (_, __, defaultDoms) => [defaultDoms.delete],
            }}
            recordCreatorProps={{
              newRecordType: 'dataSource',
              record: () => ({ id: `new-${Date.now()}` }),
              creatorButtonText: '+ Add Line',
            }}
            scroll={{ x: 1100 }}
            size="small"
          />
          <Row justify="end" style={{ marginTop: 12 }}>
            <Space size="large">
              <Typography.Text type="secondary">
                Subtotal: MYR {totals.subtotal.toFixed(2)}
              </Typography.Text>
              <Typography.Text type="secondary">
                Tax: MYR {totals.tax.toFixed(2)}
              </Typography.Text>
              <Typography.Text strong>
                Total: MYR {totals.total.toFixed(2)}
              </Typography.Text>
            </Space>
          </Row>
        </Card>
      </ProForm>
    </Card>
  )
}
