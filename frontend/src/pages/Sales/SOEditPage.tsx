import {
  EditableProTable,
  ProForm,
  ProFormDatePicker,
  ProFormDigit,
  ProFormSelect,
  ProFormTextArea,
  type EditableFormInstance,
  type ProColumns,
  type ProFormInstance,
} from '@ant-design/pro-components'
import { App, Card, Row, Skeleton, Space, Typography } from 'antd'
import dayjs from 'dayjs'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import StockStatusBadge, { type StockSnapshot } from '../../components/StockStatusBadge'
import { getTaxRatePercent } from '../../utils/taxRate'

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
  current_stock?: StockSnapshot
}

const CURRENCY_OPTIONS = [
  { value: 'MYR', label: 'MYR' },
  { value: 'SGD', label: 'SGD' },
  { value: 'USD', label: 'USD' },
  { value: 'CNY', label: 'CNY' },
]

export default function SOEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isCreate = !id
  const navigate = useNavigate()
  const { message } = App.useApp()

  const [initialValues, setInitialValues] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(!isCreate)
  const [lines, setLines] = useState<LineRow[]>([])
  const [editableKeys, setEditableKeys] = useState<(string | number)[]>([])

  const [customerOptions, setCustomerOptions] = useState<{ value: number; label: string }[]>([])
  const [warehouseOptions, setWarehouseOptions] = useState<{ value: number; label: string }[]>([])
  const [skuOptions, setSkuOptions] = useState<{ value: number; label: string; code: string }[]>([])
  const [skuLoading, setSkuLoading] = useState(false)
  const [uomOptions, setUomOptions] = useState<{ value: number; label: string }[]>([])
  const [taxRateOptions, setTaxRateOptions] = useState<{ value: number; label: string; rate: number }[]>([])

  const editableFormRef = useRef<EditableFormInstance<LineRow>>()
  const formRef = useRef<ProFormInstance<Record<string, unknown>>>()

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
            code: s.code,
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

  // Fetch on-hand/available/etc. for a single line at the given warehouse,
  // and write it into the row's `current_stock` so the Stock column updates.
  const fetchStockForLine = useCallback(
    async (skuId: number, warehouseId: number, rowId: string | number) => {
      if (!skuId || !warehouseId) return
      try {
        const res = await axiosInstance.get(
          `/inventory/stocks?sku_id=${skuId}&warehouse_id=${warehouseId}`,
        )
        const snapshot = res.data as StockSnapshot
        editableFormRef.current?.setRowData?.(rowId, { current_stock: snapshot })
        setLines((prev) =>
          prev.map((l) => (l.id === rowId ? { ...l, current_stock: snapshot } : l)),
        )
      } catch {
        // silent — leave row's stock blank, user can still proceed
      }
    },
    [],
  )

  // Refresh stock for every existing line — used when warehouse changes or
  // when an existing SO has just been loaded.
  const refreshAllStock = useCallback(
    (warehouseId: number | undefined) => {
      if (!warehouseId) return
      for (const l of lines) {
        const live = editableFormRef.current?.getRowData?.(l.id)
        const skuId = (live?.sku_id ?? l.sku_id) as number | undefined
        if (skuId) void fetchStockForLine(skuId, warehouseId, l.id)
      }
    },
    [lines, fetchStockForLine],
  )

  const handleSkuChange = useCallback(
    async (skuId: number, rowId: string | number) => {
      if (!skuId) return
      try {
        const res = await axiosInstance.get(`/skus/${skuId}`)
        const sku = res.data
        const taxRatePercent =
          getTaxRatePercent(taxRateOptions, sku.tax_rate_id) ||
          parseFloat(sku.tax_rate?.rate ?? '0')
        const autoFill = {
          uom_id: sku.base_uom_id,
          unit_price_excl_tax: parseFloat(sku.unit_price_excl_tax),
          tax_rate_id: sku.tax_rate_id,
          tax_rate_percent: taxRatePercent,
        }
        editableFormRef.current?.setRowData?.(rowId, autoFill)
        setLines((prev) => prev.map((l) => (l.id === rowId ? { ...l, ...autoFill } : l)))
      } catch {
        // user can fill manually
      }
      const wh = formRef.current?.getFieldValue('warehouse_id') as number | undefined
      if (wh) void fetchStockForLine(skuId, wh, rowId)
    },
    [taxRateOptions, fetchStockForLine],
  )

  // When the user changes only the Tax Rate dropdown (no SKU change),
  // sync tax_rate_percent so real-time totals + the submit payload reflect
  // the new rate. Backend is also authoritative on save, but the UX needs
  // the percent in form state to compute totals before submit.
  const handleTaxRateChange = useCallback(
    (taxRateId: number, rowId: string | number) => {
      if (!taxRateId) return
      const newPct = getTaxRatePercent(taxRateOptions, taxRateId)
      editableFormRef.current?.setRowData?.(rowId, { tax_rate_percent: newPct })
      setLines((prev) =>
        prev.map((l) => (l.id === rowId ? { ...l, tax_rate_percent: newPct } : l)),
      )
    },
    [taxRateOptions],
  )

  // ── Load reference data on mount ─────────────────────────────────────────
  useEffect(() => {
    fetchSkus('')

    Promise.allSettled([
      axiosInstance.get('/customers?page_size=50'),
      axiosInstance.get('/warehouses?page_size=50'),
      axiosInstance.get('/uoms?page_size=100'),
      axiosInstance.get('/tax-rates?page_size=50'),
    ]).then(([cust, wh, uom, tax]) => {
      let anyFailed = false

      if (cust.status === 'fulfilled') {
        setCustomerOptions(
          cust.value.data.items.map((c: { id: number; name: string }) => ({ value: c.id, label: c.name }))
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
        .get(`/sales-orders/${id}`)
        .then((res) => {
          const so = res.data
          setInitialValues({
            customer_id: so.customer_id,
            warehouse_id: so.warehouse_id,
            business_date: so.business_date,
            expected_ship_date: so.expected_ship_date,
            currency: so.currency,
            exchange_rate: parseFloat(so.exchange_rate),
            payment_terms_days: so.payment_terms_days,
            shipping_address: so.shipping_address,
            shipping_amount: parseFloat(so.shipping_amount ?? '0'),
            remarks: so.remarks,
          })
          const loadedLines: LineRow[] = so.lines.map((l: {
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
          setEditableKeys(loadedLines.map((l) => l.id))
          if (so.warehouse_id) {
            queueMicrotask(() => {
              for (const l of loadedLines) {
                if (l.sku_id) void fetchStockForLine(l.sku_id, so.warehouse_id, l.id)
              }
            })
          }
        })
        .catch(() => message.error('Failed to load sales order'))
        .finally(() => setLoading(false))
    }
  }, [id, isCreate, message, fetchSkus, fetchStockForLine])

  const lineColumns: ProColumns<LineRow>[] = [
    {
      title: 'SKU',
      dataIndex: 'sku_id',
      valueType: 'select',
      fieldProps: {
        options: skuOptions,
        showSearch: true,
        allowClear: true,
        filterOption: false,
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
      title: 'Stock',
      dataIndex: 'current_stock',
      editable: false,
      width: 140,
      render: (_, row) =>
        row.current_stock ? (
          <StockStatusBadge stock={row.current_stock} compact />
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
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
      // Always derive from tax_rate_id (the dropdown's authoritative value).
      // Don't trust l.tax_rate_percent — it can desync with tax_rate_id in
      // edge cases (e.g. when EditableProTable's batched onValuesChange
      // captures only the changed field and tax_rate_percent retains its
      // pre-change value). Backend re-derives from id on save anyway.
      const taxPct = getTaxRatePercent(taxRateOptions, l.tax_rate_id)
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
    const fmtDate = (v: unknown) => (dayjs.isDayjs(v) ? v.format('YYYY-MM-DD') : v)

    const filledLines = lines.filter((l) => l.sku_id != null)
    if (filledLines.length === 0) {
      message.error('Please add at least one order line.')
      return
    }

    const payload = {
      ...values,
      business_date: fmtDate(values.business_date),
      expected_ship_date: fmtDate(values.expected_ship_date),
      shipping_amount: values.shipping_amount ?? 0,
      lines: filledLines.map((l) => ({
        sku_id: l.sku_id,
        uom_id: l.uom_id,
        description: l.description,
        qty_ordered: l.qty_ordered,
        unit_price_excl_tax: l.unit_price_excl_tax,
        tax_rate_id: l.tax_rate_id,
        // Derive from tax_rate_id (single source of truth); backend ignores
        // this field anyway and looks up the rate by tax_rate_id.
        tax_rate_percent: getTaxRatePercent(taxRateOptions, l.tax_rate_id),
        discount_percent: l.discount_percent ?? 0,
      })),
    }
    try {
      if (isCreate) {
        await axiosInstance.post('/sales-orders', payload)
        message.success('Sales order created.')
      } else {
        await axiosInstance.patch(`/sales-orders/${id}`, payload)
        message.success('Sales order updated.')
      }
      navigate('/sales/orders')
    } catch (err: unknown) {
      const errData = (err as { response?: { data?: { message?: string; detail?: unknown } } })?.response?.data
      const msg = errData?.message ?? 'Operation failed'
      message.error(msg)
    }
  }

  if (loading) return <Skeleton active />

  return (
    <Card title={isCreate ? 'New Sales Order' : 'Edit Sales Order'}>
      <ProForm
        formRef={formRef}
        initialValues={initialValues ?? {
          currency: 'MYR',
          exchange_rate: 1,
          payment_terms_days: 30,
          shipping_amount: 0,
        }}
        onFinish={handleSubmit}
        onReset={() => navigate('/sales/orders')}
      >
        <ProForm.Group title="Order Details">
          <ProFormSelect
            name="customer_id"
            label="Customer"
            options={customerOptions}
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
            fieldProps={{
              onChange: (wh: number) => refreshAllStock(wh),
            }}
          />
          <ProFormDatePicker name="business_date" label="Order Date" rules={[{ required: true }]} width="md" />
          <ProFormDatePicker name="expected_ship_date" label="Expected Ship Date" width="md" />
        </ProForm.Group>

        <ProForm.Group title="Payment">
          <ProFormSelect name="currency" label="Currency" options={CURRENCY_OPTIONS} width="sm" />
          <ProFormDigit name="exchange_rate" label="Exchange Rate" min={0.000001} fieldProps={{ precision: 8 }} width="sm" />
          <ProFormDigit name="payment_terms_days" label="Payment Terms (Days)" min={0} width="sm" />
          <ProFormDigit name="shipping_amount" label="Shipping Amount" min={0} fieldProps={{ precision: 2 }} width="sm" />
        </ProForm.Group>

        <ProFormTextArea name="shipping_address" label="Shipping Address" fieldProps={{ rows: 2 }} />
        <ProFormTextArea name="remarks" label="Remarks" fieldProps={{ rows: 2 }} />

        <Card title="Order Lines" size="small" style={{ marginBottom: 24 }}>
          <EditableProTable<LineRow>
            rowKey="id"
            editableFormRef={editableFormRef}
            value={lines}
            onChange={(v) => setLines(v as LineRow[])}
            columns={lineColumns}
            editable={{
              type: 'multiple',
              editableKeys,
              onChange: (keys) => setEditableKeys(keys as (string | number)[]),
              onValuesChange: (record: LineRow, allValues: LineRow[]) => {
                setLines(allValues)
                const prev = lines.find((l) => l.id === record.id)
                if (record.sku_id != null && record.sku_id !== prev?.sku_id) {
                  handleSkuChange(record.sku_id, record.id)
                } else if (
                  record.tax_rate_id != null &&
                  record.tax_rate_id !== prev?.tax_rate_id
                ) {
                  handleTaxRateChange(record.tax_rate_id, record.id)
                }
              },
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
