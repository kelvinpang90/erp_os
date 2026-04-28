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

const SHIPPING_METHOD_OPTIONS = [
  { value: 'COURIER', label: 'Courier' },
  { value: 'OWN_FLEET', label: 'Own Fleet' },
  { value: 'CUSTOMER_PICKUP', label: 'Customer Pickup' },
  { value: 'THIRD_PARTY', label: 'Third Party Logistics' },
]

export default function DOCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { message } = App.useApp()

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
          message.warning('Selected SO is not shippable (must be CONFIRMED or PARTIAL_SHIPPED).')
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
      .catch(() => message.error('Failed to load sales order'))
      .finally(() => setSoLoading(false))
  }, [selectedSoId, message])

  const lineColumns: ProColumns<DOLineRow>[] = [
    {
      title: '#',
      dataIndex: 'line_no',
      width: 50,
      editable: false,
    },
    {
      title: 'SKU',
      dataIndex: 'sku_code',
      width: 240,
      editable: false,
      render: (_, row) => (row.sku_code ? `${row.sku_code} — ${row.sku_name}` : '-'),
    },
    {
      title: 'Qty Ordered',
      dataIndex: 'qty_ordered',
      width: 100,
      align: 'right',
      editable: false,
      render: (val) => Number(val).toLocaleString('en-MY'),
    },
    {
      title: 'Already Shipped',
      dataIndex: 'qty_already_shipped',
      width: 130,
      align: 'right',
      editable: false,
      render: (val) => Number(val).toLocaleString('en-MY'),
    },
    {
      title: 'Remaining',
      dataIndex: 'qty_remaining',
      width: 100,
      align: 'right',
      editable: false,
      render: (val) => (
        <Typography.Text strong>{Number(val).toLocaleString('en-MY')}</Typography.Text>
      ),
    },
    {
      title: 'Qty to Ship',
      dataIndex: 'qty_shipped',
      valueType: 'digit',
      width: 130,
      align: 'right',
      fieldProps: { min: 0, precision: 4 },
      formItemProps: {
        rules: [
          { required: true, message: 'Quantity is required' },
          {
            validator: async (_rule: unknown, value: unknown) => {
              if (value === undefined || value === null) return
              const num = Number(value)
              if (Number.isNaN(num) || num <= 0) {
                throw new Error('Quantity must be > 0')
              }
            },
          },
        ],
      },
    },
    {
      title: 'Batch No',
      dataIndex: 'batch_no',
      width: 120,
    },
    {
      title: 'Expiry Date',
      dataIndex: 'expiry_date',
      valueType: 'date',
      width: 140,
    },
    {
      title: 'Serial No',
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
      message.error('Please select a sales order first.')
      return
    }
    const fmtDate = (v: unknown) =>
      dayjs.isDayjs(v) ? v.format('YYYY-MM-DD') : (v as string | undefined)

    const filledLines = lines.filter(
      (l) => l.qty_shipped !== undefined && Number(l.qty_shipped) > 0,
    )
    if (filledLines.length === 0) {
      message.error('Please specify quantity for at least one line.')
      return
    }

    // Client-side over-shipment check (backend remains source of truth)
    const overShip = filledLines.find(
      (l) => Number(l.qty_shipped ?? 0) > l.qty_remaining,
    )
    if (overShip) {
      message.error(
        `Line ${overShip.line_no}: cannot ship more than remaining ${overShip.qty_remaining}.`,
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
      message.success(`${res.data.document_no} created. Stock updated.`)
      navigate(`/sales/delivery/${res.data.id}`)
    } catch (err: unknown) {
      const errData = (err as { response?: { data?: { message?: string; error_code?: string } } })
        ?.response?.data
      message.error(errData?.message ?? 'Failed to create delivery order')
    }
  }

  return (
    <Card title="Create Delivery Order">
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <ProFormSelect
          label="Sales Order"
          placeholder="Select a confirmed sales order"
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
                submitText: 'Create',
                resetText: 'Cancel',
              },
            }}
          >
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message={
                <Space>
                  <span>Sales Order: <strong>{so.document_no}</strong></span>
                  <Tag color={so.status === 'CONFIRMED' ? 'blue' : 'gold'}>
                    {so.status.replace(/_/g, ' ')}
                  </Tag>
                  <span>Warehouse: #{so.warehouse_id}</span>
                </Space>
              }
            />

            {lines.length === 0 ? (
              <Alert type="warning" showIcon message="All SO lines are already fully shipped." />
            ) : (
              <>
                <ProForm.Group>
                  <ProFormDatePicker
                    name="delivery_date"
                    label="Delivery Date"
                    rules={[{ required: true }]}
                    width="md"
                  />
                  <ProFormSelect
                    name="shipping_method"
                    label="Shipping Method"
                    options={SHIPPING_METHOD_OPTIONS}
                    width="md"
                  />
                  <ProFormText name="tracking_no" label="Tracking No." width="md" />
                </ProForm.Group>

                <ProFormTextArea name="remarks" label="Remarks" fieldProps={{ rows: 2 }} />

                <Card title="Lines" size="small" style={{ marginBottom: 24 }}>
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
                      Total Qty: {totalsHint.total.toLocaleString('en-MY', { maximumFractionDigits: 4 })}
                    </Typography.Text>
                  </Space>
                </Card>
              </>
            )}
          </ProForm>
        ) : (
          <Alert type="info" showIcon message="Please select a sales order first." />
        )}
      </Space>
    </Card>
  )
}
