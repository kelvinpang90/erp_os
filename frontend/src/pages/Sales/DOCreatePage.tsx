import {
  EditableProTable,
  ProForm,
  ProFormDatePicker,
  ProFormSelect,
  ProFormText,
  ProFormTextArea,
  type EditableFormInstance,
  type ProColumns,
} from '@ant-design/pro-components'
import { App, Alert, Card, Skeleton, Space, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface SOLineFromAPI {
  id: number
  line_no: number
  sku_id: number
  sku_code: string
  sku_name: string
  uom_id: number
  qty_ordered: string
  qty_shipped: string
}

interface SODetail {
  id: number
  document_no: string
  status: string
  warehouse_id: number
  currency: string
  lines: SOLineFromAPI[]
}

interface DOLineRow {
  id: number  // SO line id (we use it as table row key)
  sales_order_line_id: number
  line_no: number
  sku_id: number
  sku_code: string
  sku_name: string
  uom_id: number
  qty_ordered: number
  qty_already_shipped: number
  qty_remaining: number
  qty_shipped?: number
  batch_no?: string
  expiry_date?: string
  serial_no?: string
}

const SHIPPABLE_SO_STATUSES = ['CONFIRMED', 'PARTIAL_SHIPPED']

export default function DOCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { message } = App.useApp()
  const { t } = useTranslation(['delivery_order', 'common'])

  const SHIPPING_METHOD_OPTIONS = [
    { value: 'COURIER', label: t('shipping_method_options.COURIER') },
    { value: 'OWN_FLEET', label: t('shipping_method_options.OWN_FLEET') },
    { value: 'CUSTOMER_PICKUP', label: t('shipping_method_options.CUSTOMER_PICKUP') },
    { value: 'THIRD_PARTY', label: t('shipping_method_options.THIRD_PARTY') },
  ]

  const initialSoId = searchParams.get('so_id')
  const [selectedSoId, setSelectedSoId] = useState<number | null>(
    initialSoId ? Number(initialSoId) : null,
  )
  const [soOptions, setSoOptions] = useState<{ value: number; label: string }[]>([])
  const [so, setSO] = useState<SODetail | null>(null)
  const [soLoading, setSoLoading] = useState(false)
  const [lines, setLines] = useState<DOLineRow[]>([])
  const [editableKeys, setEditableKeys] = useState<(string | number)[]>([])

  const editableFormRef = useRef<EditableFormInstance<DOLineRow>>()

  // Load shippable SOs for the dropdown.
  useEffect(() => {
    Promise.all(
      SHIPPABLE_SO_STATUSES.map((s) =>
        axiosInstance.get(`/sales-orders?status=${s}&page_size=100`),
      ),
    )
      .then((results) => {
        const items: { id: number; document_no: string; status: string }[] = []
        for (const r of results) items.push(...r.data.items)
        setSoOptions(
          items.map((s) => ({
            value: s.id,
            label: `${s.document_no} (${s.status.replace(/_/g, ' ')})`,
          })),
        )
      })
      .catch(() => {/* dropdown stays empty */})
  }, [])

  // Load SO detail + populate line rows when an SO is selected.
  useEffect(() => {
    if (!selectedSoId) {
      setSO(null)
      setLines([])
      setEditableKeys([])
      return
    }
    setSoLoading(true)
    axiosInstance
      .get(`/sales-orders/${selectedSoId}`)
      .then((res) => {
        const detail: SODetail = res.data
        if (!SHIPPABLE_SO_STATUSES.includes(detail.status)) {
          message.warning(t('errors.SO_NOT_SHIPPABLE'))
          setSO(null)
          setLines([])
          setEditableKeys([])
          return
        }
        setSO(detail)
        const rows: DOLineRow[] = detail.lines
          .map((l) => {
            const ordered = parseFloat(l.qty_ordered)
            const already = parseFloat(l.qty_shipped)
            const remaining = Math.max(ordered - already, 0)
            return {
              id: l.id,
              sales_order_line_id: l.id,
              line_no: l.line_no,
              sku_id: l.sku_id,
              sku_code: l.sku_code,
              sku_name: l.sku_name,
              uom_id: l.uom_id,
              qty_ordered: ordered,
              qty_already_shipped: already,
              qty_remaining: remaining,
              qty_shipped: remaining > 0 ? remaining : undefined,
            }
          })
          .filter((r) => r.qty_remaining > 0)
        setLines(rows)
        setEditableKeys(rows.map((r) => r.id))
      })
      .catch(() => message.error(t('messages.loadSoFailed')))
      .finally(() => setSoLoading(false))
  }, [selectedSoId, message, t])

  const lineColumns: ProColumns<DOLineRow>[] = [
    {
      title: t('line_no'),
      dataIndex: 'line_no',
      width: 50,
      editable: false,
    },
    {
      title: t('sku'),
      dataIndex: 'sku_code',
      width: 240,
      editable: false,
      render: (_, row) => (row.sku_code ? `${row.sku_code} — ${row.sku_name}` : '-'),
    },
    {
      title: t('qty_ordered'),
      dataIndex: 'qty_ordered',
      width: 100,
      align: 'right',
      editable: false,
      render: (val) => Number(val).toLocaleString('en-MY'),
    },
    {
      title: t('qty_already_shipped'),
      dataIndex: 'qty_already_shipped',
      width: 130,
      align: 'right',
      editable: false,
      render: (val) => Number(val).toLocaleString('en-MY'),
    },
    {
      title: t('qty_remaining'),
      dataIndex: 'qty_remaining',
      width: 100,
      align: 'right',
      editable: false,
      render: (val) => (
        <Typography.Text strong>{Number(val).toLocaleString('en-MY')}</Typography.Text>
      ),
    },
    {
      title: t('qty_shipped'),
      dataIndex: 'qty_shipped',
      valueType: 'digit',
      width: 130,
      align: 'right',
      fieldProps: { min: 0, precision: 4 },
      formItemProps: {
        rules: [
          { required: true, message: t('validation_qty_required') },
          {
            validator: async (_rule: unknown, value: unknown) => {
              if (value === undefined || value === null) return
              const num = Number(value)
              if (Number.isNaN(num) || num <= 0) {
                throw new Error(t('validation_qty_required'))
              }
            },
          },
        ],
      },
    },
    {
      title: t('batch_no'),
      dataIndex: 'batch_no',
      width: 120,
    },
    {
      title: t('expiry_date'),
      dataIndex: 'expiry_date',
      valueType: 'date',
      width: 140,
    },
    {
      title: t('serial_no'),
      dataIndex: 'serial_no',
      width: 140,
    },
  ]

  const totalsHint = useMemo(() => {
    let total = 0
    for (const l of lines) {
      total += Number(l.qty_shipped ?? 0)
    }
    return { total }
  }, [lines])

  const handleSubmit = async (values: Record<string, unknown>) => {
    if (!selectedSoId || !so) {
      message.error(t('validation_select_so_first'))
      return
    }
    const fmtDate = (v: unknown) =>
      dayjs.isDayjs(v) ? v.format('YYYY-MM-DD') : (v as string | undefined)

    const filledLines = lines.filter(
      (l) => l.qty_shipped !== undefined && Number(l.qty_shipped) > 0,
    )
    if (filledLines.length === 0) {
      message.error(t('validation_at_least_one_line'))
      return
    }

    // Client-side over-shipment check (backend remains source of truth)
    const overShip = filledLines.find(
      (l) => Number(l.qty_shipped ?? 0) > l.qty_remaining,
    )
    if (overShip) {
      message.error(
        t('messages.overShipLine', { lineNo: overShip.line_no, remaining: overShip.qty_remaining }),
      )
      return
    }

    const payload = {
      sales_order_id: selectedSoId,
      delivery_date: fmtDate(values.delivery_date),
      shipping_method: values.shipping_method || null,
      tracking_no: values.tracking_no || null,
      remarks: values.remarks || null,
      lines: filledLines.map((l) => ({
        sales_order_line_id: l.sales_order_line_id,
        qty_shipped: l.qty_shipped,
        batch_no: l.batch_no || undefined,
        expiry_date: fmtDate(l.expiry_date) || undefined,
        serial_no: l.serial_no || undefined,
      })),
    }

    try {
      const res = await axiosInstance.post('/delivery-orders', payload)
      message.success(t('messages.created', { docNo: res.data.document_no }))
      navigate(`/sales/delivery/${res.data.id}`)
    } catch (err: unknown) {
      const errData = (err as { response?: { data?: { message?: string; error_code?: string } } })
        ?.response?.data
      message.error(errData?.message ?? t('messages.createFailed'))
    }
  }

  return (
    <Card title={t('create_for_so')}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <ProFormSelect
          label={t('select_so')}
          placeholder={t('select_so_placeholder')}
          options={soOptions}
          fieldProps={{
            value: selectedSoId ?? undefined,
            showSearch: true,
            filterOption: (input, option) =>
              String(option?.label ?? '').toLowerCase().includes(input.toLowerCase()),
            onChange: (v) => setSelectedSoId((v as number) ?? null),
          }}
          width="lg"
        />

        {soLoading ? (
          <Skeleton active />
        ) : so ? (
          <ProForm
            initialValues={{
              delivery_date: dayjs(),
              shipping_method: 'COURIER',
            }}
            onFinish={handleSubmit}
            onReset={() => navigate('/sales/delivery')}
            submitter={{
              searchConfig: {
                submitText: t('common:create'),
                resetText: t('common:cancel'),
              },
            }}
          >
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message={
                <Space>
                  <span>{t('sales_order')}: <strong>{so.document_no}</strong></span>
                  <Tag color={so.status === 'CONFIRMED' ? 'blue' : 'gold'}>
                    {so.status.replace(/_/g, ' ')}
                  </Tag>
                  <span>{t('warehouse')}: #{so.warehouse_id}</span>
                </Space>
              }
            />

            {lines.length === 0 ? (
              <Alert type="warning" showIcon message={t('no_lines_to_ship')} />
            ) : (
              <>
                <ProForm.Group>
                  <ProFormDatePicker
                    name="delivery_date"
                    label={t('delivery_date')}
                    rules={[{ required: true }]}
                    width="md"
                  />
                  <ProFormSelect
                    name="shipping_method"
                    label={t('shipping_method')}
                    options={SHIPPING_METHOD_OPTIONS}
                    width="md"
                  />
                  <ProFormText name="tracking_no" label={t('tracking_no')} width="md" />
                </ProForm.Group>

                <ProFormTextArea name="remarks" label={t('remarks')} fieldProps={{ rows: 2 }} />

                <Card title={t('lines')} size="small" style={{ marginBottom: 24 }}>
                  <EditableProTable<DOLineRow>
                    rowKey="id"
                    editableFormRef={editableFormRef}
                    value={lines}
                    onChange={(v) => setLines(v as DOLineRow[])}
                    columns={lineColumns}
                    editable={{
                      type: 'multiple',
                      editableKeys,
                      onChange: (keys) => setEditableKeys(keys as (string | number)[]),
                      onValuesChange: (_record: DOLineRow, allValues: DOLineRow[]) => {
                        setLines(allValues)
                      },
                      actionRender: () => [],
                    }}
                    recordCreatorProps={false}
                    scroll={{ x: 1300 }}
                    size="small"
                  />
                  <Space size="large" style={{ marginTop: 12, justifyContent: 'flex-end', width: '100%' }}>
                    <Typography.Text strong>
                      {t('totalQty')}: {totalsHint.total.toLocaleString('en-MY', { maximumFractionDigits: 4 })}
                    </Typography.Text>
                  </Space>
                </Card>
              </>
            )}
          </ProForm>
        ) : (
          <Alert type="info" showIcon message={t('validation_select_so_first')} />
        )}
      </Space>
    </Card>
  )
}
