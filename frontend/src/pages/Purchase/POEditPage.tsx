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
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import StockStatusBadge, { type StockSnapshot } from '../../components/StockStatusBadge'
import { getTaxRatePercent } from '../../utils/taxRate'
import type { OCRPurchaseOrderResult } from './OCRUploadPage'

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

export default function POEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isCreate = !id
  const navigate = useNavigate()
  const location = useLocation()
  const { message } = App.useApp()

  // OCR prefill payload (when arriving from /purchase/orders/ocr-upload).
  // Only meaningful on create; ignored when editing an existing PO.
  const ocrPrefill = isCreate
    ? ((location.state as { ocrPrefill?: OCRPurchaseOrderResult } | null)?.ocrPrefill ?? null)
    : null

  const [initialValues, setInitialValues] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(!isCreate)
  const [lines, setLines] = useState<LineRow[]>([])
  const [editableKeys, setEditableKeys] = useState<(string | number)[]>([])
  const [ocrApplied, setOcrApplied] = useState(false)

  const [supplierOptions, setSupplierOptions] = useState<{ value: number; label: string }[]>([])
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

  // Refresh stock for every existing line — used when the warehouse changes
  // or when an existing PO/lines have just been loaded.
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
        // silently ignore — user can fill manually
      }
      // Stock fetch is independent of the SKU detail call — even if /skus/:id
      // fails the user might still want to see live stock.
      const wh = formRef.current?.getFieldValue('warehouse_id') as number | undefined
      if (wh) void fetchStockForLine(skuId, wh, rowId)
    },
    [taxRateOptions, fetchStockForLine],
  )

  // Sync tax_rate_percent when the user changes only the Tax Rate dropdown
  // (no SKU change). Backend is authoritative on save, but real-time totals
  // need this in form state. See SOEditPage for the same pattern.
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

    // Editing an existing PO — load it. OCR prefill (create-only) is handled
    // by a separate effect once the reference dropdowns are populated.
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
          setEditableKeys(loadedLines.map((l) => l.id))
          // Populate Stock column for each loaded line. Done in a microtask so
          // setLines/setEditableKeys commit first and EditableProTable's row
          // form refs are wired up before we try setRowData.
          if (po.warehouse_id) {
            queueMicrotask(() => {
              for (const l of loadedLines) {
                if (l.sku_id) void fetchStockForLine(l.sku_id, po.warehouse_id, l.id)
              }
            })
          }
        })
        .catch(() => message.error('Failed to load purchase order'))
        .finally(() => setLoading(false))
    }
  }, [id, isCreate, message, fetchSkus, fetchStockForLine])

  // ── OCR prefill: apply once reference dropdowns are populated ──────────
  // SKUs aren't matched against the local cache (which only has the first 50
  // alphabetically) — instead we fire a server-side lookup per unique sku_code
  // to avoid pagination misses.
  useEffect(() => {
    if (!ocrPrefill || ocrApplied) return
    const refsReady =
      supplierOptions.length > 0 &&
      warehouseOptions.length > 0 &&
      uomOptions.length > 0 &&
      taxRateOptions.length > 0
    if (!refsReady) return

    const num = (v: string | number | null | undefined): number | undefined => {
      if (v === null || v === undefined || v === '') return undefined
      const n = typeof v === 'string' ? parseFloat(v) : v
      return Number.isFinite(n) ? n : undefined
    }

    const matchUom = (uom: string | null): number | undefined => {
      if (!uom) return undefined
      const lc = uom.trim().toLowerCase()
      return uomOptions.find((u) => u.label.toLowerCase() === lc)?.value
    }

    const matchTaxRate = (pct: number | undefined): { id?: number; rate: number } => {
      if (pct === undefined) return { rate: 0 }
      // Find an exact rate match within 0.01 tolerance
      const hit = taxRateOptions.find((t) => Math.abs(t.rate - pct) < 0.01)
      return { id: hit?.value, rate: pct }
    }

    setOcrApplied(true)  // claim the prefill slot first so we don't race on re-renders

    const apply = async () => {
      // 1. Match supplier from the cached options (50 should cover the common case)
      let supplierId: number | undefined
      const ocrName = (ocrPrefill.supplier_name ?? '').trim().toLowerCase()
      if (ocrName) {
        const hit = supplierOptions.find(
          (s) => s.label.toLowerCase() === ocrName ||
                 s.label.toLowerCase().includes(ocrName) ||
                 ocrName.includes(s.label.toLowerCase()),
        )
        supplierId = hit?.value
      }

      // 2. Resolve SKUs by server-side search per unique code. Each call is a
      //    LIKE %code% search; we filter to exact code match in the response.
      type ServerSku = {
        id: number; code: string; name: string;
        base_uom_id?: number;
        unit_price_excl_tax?: string;
        tax_rate_id?: number;
        tax_rate?: { rate?: string };
      }
      const codes = Array.from(new Set(
        ocrPrefill.lines
          .map((l) => l.sku_code?.trim())
          .filter((c): c is string => !!c),
      ))
      const skuByCode = new Map<string, ServerSku>()

      await Promise.all(codes.map(async (code) => {
        try {
          const res = await axiosInstance.get(
            `/skus?page_size=10&search=${encodeURIComponent(code)}`,
          )
          const exact = (res.data.items as ServerSku[]).find(
            (s) => s.code.toLowerCase() === code.toLowerCase(),
          )
          if (exact) skuByCode.set(code.toLowerCase(), exact)
        } catch {
          // ignore — line will fall back to "Please select"
        }
      }))

      // 3. Make sure the matched SKUs are in the dropdown options so the
      //    select widget can render their labels.
      if (skuByCode.size > 0) {
        setSkuOptions((prev) => {
          const seen = new Set(prev.map((o) => o.value))
          const additions = Array.from(skuByCode.values())
            .filter((s) => !seen.has(s.id))
            .map((s) => ({ value: s.id, label: `${s.code} — ${s.name}`, code: s.code }))
          return additions.length > 0 ? [...prev, ...additions] : prev
        })
      }

      // 4. Header
      const headerValues: Record<string, unknown> = {
        currency: (ocrPrefill.currency ?? 'MYR').toUpperCase(),
        exchange_rate: 1,
        payment_terms_days: 30,
      }
      if (supplierId !== undefined) headerValues.supplier_id = supplierId
      if (ocrPrefill.business_date) headerValues.business_date = dayjs(ocrPrefill.business_date)
      if (ocrPrefill.remarks) headerValues.remarks = ocrPrefill.remarks

      setInitialValues((prev) => ({ ...(prev ?? {}), ...headerValues }))
      formRef.current?.setFieldsValue(headerValues)

      // 5. Lines — prefer SKU's own UOM/tax/price when we have the SKU; fall
      //    back to whatever OCR returned if the SKU wasn't found.
      const newLines: LineRow[] = ocrPrefill.lines.map((line, idx) => {
        const code = line.sku_code?.trim().toLowerCase()
        const sku = code ? skuByCode.get(code) : undefined

        const ocrTax = matchTaxRate(num(line.tax_rate_percent))
        const skuTaxRateId = sku?.tax_rate_id
        const skuTaxRatePct = sku?.tax_rate?.rate ? parseFloat(sku.tax_rate.rate) : undefined

        return {
          id: `ocr-${idx}-${Date.now()}`,
          sku_id: sku?.id,
          uom_id: sku?.base_uom_id ?? matchUom(line.uom),
          description: line.description,
          qty_ordered: num(line.qty),
          unit_price_excl_tax:
            num(line.unit_price_excl_tax) ??
            (sku?.unit_price_excl_tax ? parseFloat(sku.unit_price_excl_tax) : undefined),
          tax_rate_id: skuTaxRateId ?? ocrTax.id,
          tax_rate_percent: skuTaxRatePct ?? ocrTax.rate,
          discount_percent: num(line.discount_percent) ?? 0,
        }
      })
      setLines(newLines)
      setEditableKeys(newLines.map((l) => l.id))

      // Populate Stock column for OCR-prefilled lines if warehouse is set.
      const whAfterOcr = formRef.current?.getFieldValue('warehouse_id') as number | undefined
      if (whAfterOcr) {
        queueMicrotask(() => {
          for (const l of newLines) {
            if (l.sku_id) void fetchStockForLine(l.sku_id, whAfterOcr, l.id)
          }
        })
      }

      // 6. Tell user what to review
      const missing: string[] = []
      if (ocrPrefill.supplier_name && supplierId === undefined) missing.push('supplier')
      const linesMissingSku = newLines.filter((l) => l.sku_id === undefined).length
      if (linesMissingSku > 0) missing.push(`${linesMissingSku} SKU`)
      if (missing.length > 0) {
        message.warning(
          `OCR prefilled. Please review unmatched fields: ${missing.join(', ')}.`,
        )
      } else {
        message.success(`OCR prefilled (confidence: ${ocrPrefill.confidence}). Please review and save.`)
      }
    }

    void apply()
  }, [
    ocrPrefill,
    ocrApplied,
    supplierOptions,
    warehouseOptions,
    uomOptions,
    taxRateOptions,
    message,
    fetchStockForLine,
  ])

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
      // Always derive from tax_rate_id — never trust l.tax_rate_percent
      // because EditableProTable batching can desync it from tax_rate_id.
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
    // ProFormDatePicker returns dayjs objects — Pydantic v2 date field only accepts "YYYY-MM-DD"
    const fmtDate = (v: unknown) => (dayjs.isDayjs(v) ? v.format('YYYY-MM-DD') : v)

    const filledLines = lines.filter((l) => l.sku_id != null)
    if (filledLines.length === 0) {
      message.error('Please add at least one order line.')
      return
    }

    const payload = {
      ...values,
      business_date: fmtDate(values.business_date),
      expected_date: fmtDate(values.expected_date),
      lines: filledLines.map((l) => ({
        sku_id: l.sku_id,
        uom_id: l.uom_id,
        description: l.description,
        qty_ordered: l.qty_ordered,
        unit_price_excl_tax: l.unit_price_excl_tax,
        tax_rate_id: l.tax_rate_id,
        // Derive from tax_rate_id; backend re-derives from id on save.
        tax_rate_percent: getTaxRatePercent(taxRateOptions, l.tax_rate_id),
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
      const errData = (err as { response?: { data?: { message?: string; detail?: unknown } } })?.response?.data
      const msg = errData?.message ?? 'Operation failed'
      message.error(msg)
    }
  }

  if (loading) return <Skeleton active />

  return (
    <Card title={isCreate ? 'New Purchase Order' : 'Edit Purchase Order'}>
      <ProForm
        formRef={formRef}
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
            fieldProps={{
              onChange: (wh: number) => refreshAllStock(wh),
            }}
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
