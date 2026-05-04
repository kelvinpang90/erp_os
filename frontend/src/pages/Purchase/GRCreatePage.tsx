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

interface POLineFromAPI {
  id: number
  line_no: number
  sku_id: number
  sku_code: string
  sku_name: string
  uom_id: number
  qty_ordered: string
  qty_received: string
  unit_price_excl_tax: string
}

interface PODetail {
  id: number
  document_no: string
  status: string
  warehouse_id: number
  currency: string
  lines: POLineFromAPI[]
}

interface GRLineRow {
  id: number  // PO line id (we use it as table row key)
  purchase_order_line_id: number
  line_no: number
  sku_id: number
  sku_code: string
  sku_name: string
  uom_id: number
  qty_ordered: number
  qty_already_received: number
  qty_remaining: number
  qty_received?: number
  unit_cost?: number
  batch_no?: string
  expiry_date?: string
  remarks?: string
}

const RECEIVABLE_PO_STATUSES = ['CONFIRMED', 'PARTIAL_RECEIVED']

// Default tolerance — must match backend env GR_OVER_RECEIPT_TOLERANCE.
// Used only for client-side hint colours; backend remains the source of truth.
const FRONTEND_TOLERANCE_HINT = 0.05

export default function GRCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { t } = useTranslation(['goods_receipt', 'common'])
  const { message } = App.useApp()

  const initialPoId = searchParams.get('po_id')
  const [selectedPoId, setSelectedPoId] = useState<number | null>(
    initialPoId ? Number(initialPoId) : null,
  )
  const [poOptions, setPoOptions] = useState<{ value: number; label: string }[]>([])
  const [po, setPO] = useState<PODetail | null>(null)
  const [poLoading, setPoLoading] = useState(false)
  const [lines, setLines] = useState<GRLineRow[]>([])
  const [editableKeys, setEditableKeys] = useState<(string | number)[]>([])

  const editableFormRef = useRef<EditableFormInstance<GRLineRow>>()

  // Load receivable POs for the dropdown.
  useEffect(() => {
    Promise.all(
      RECEIVABLE_PO_STATUSES.map((s) =>
        axiosInstance.get(`/purchase-orders?status=${s}&page_size=100`),
      ),
    )
      .then((results) => {
        const items: { id: number; document_no: string; status: string }[] = []
        for (const r of results) items.push(...r.data.items)
        setPoOptions(
          items.map((p) => ({
            value: p.id,
            label: `${p.document_no} (${p.status.replace(/_/g, ' ')})`,
          })),
        )
      })
      .catch(() => {/* dropdown stays empty; user can still pre-fill via URL */})
  }, [])

  // Load PO detail + populate line rows when a PO is selected.
  useEffect(() => {
    if (!selectedPoId) {
      setPO(null)
      setLines([])
      setEditableKeys([])
      return
    }
    setPoLoading(true)
    axiosInstance
      .get(`/purchase-orders/${selectedPoId}`)
      .then((res) => {
        const detail: PODetail = res.data
        if (!RECEIVABLE_PO_STATUSES.includes(detail.status)) {
          message.warning(t('errors.PO_NOT_RECEIVABLE'))
          setPO(null)
          setLines([])
          setEditableKeys([])
          return
        }
        setPO(detail)
        const rows: GRLineRow[] = detail.lines
          .map((l) => {
            const ordered = parseFloat(l.qty_ordered)
            const already = parseFloat(l.qty_received)
            const remaining = Math.max(ordered - already, 0)
            return {
              id: l.id,
              purchase_order_line_id: l.id,
              line_no: l.line_no,
              sku_id: l.sku_id,
              sku_code: l.sku_code,
              sku_name: l.sku_name,
              uom_id: l.uom_id,
              qty_ordered: ordered,
              qty_already_received: already,
              qty_remaining: remaining,
              qty_received: remaining > 0 ? remaining : undefined,
              unit_cost: parseFloat(l.unit_price_excl_tax),
            }
          })
          .filter((r) => r.qty_remaining > 0)
        setLines(rows)
        setEditableKeys(rows.map((r) => r.id))
      })
      .catch(() => message.error(t('messages.loadPoFailed')))
      .finally(() => setPoLoading(false))
  }, [selectedPoId, message, t])

  const lineColumns: ProColumns<GRLineRow>[] = [
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
      render: (_, row) =>
        row.sku_code ? `${row.sku_code} — ${row.sku_name}` : '-',
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
      title: t('qty_already_received'),
      dataIndex: 'qty_already_received',
      width: 120,
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
      render: (_, row) => {
        const max = row.qty_remaining * (1 + FRONTEND_TOLERANCE_HINT)
        return (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{row.qty_remaining}</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 11 }}>
              {t('qty_max_allowed')}: {max.toFixed(4).replace(/\.?0+$/, '')}
            </Typography.Text>
          </Space>
        )
      },
    },
    {
      title: t('qty_received'),
      dataIndex: 'qty_received',
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
      title: t('unit_cost'),
      dataIndex: 'unit_cost',
      valueType: 'digit',
      width: 110,
      align: 'right',
      fieldProps: { min: 0, precision: 4 },
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
      title: t('remarks'),
      dataIndex: 'remarks',
      width: 160,
    },
  ]

  const totalsHint = useMemo(() => {
    let total = 0
    let totalCost = 0
    for (const l of lines) {
      const qty = Number(l.qty_received ?? 0)
      const cost = Number(l.unit_cost ?? 0)
      total += qty
      totalCost += qty * cost
    }
    return { total, totalCost }
  }, [lines])

  const handleSubmit = async (values: Record<string, unknown>) => {
    if (!selectedPoId || !po) {
      message.error(t('validation_select_po_first'))
      return
    }
    const fmtDate = (v: unknown) =>
      dayjs.isDayjs(v) ? v.format('YYYY-MM-DD') : (v as string | undefined)

    const filledLines = lines.filter(
      (l) => l.qty_received !== undefined && Number(l.qty_received) > 0,
    )
    if (filledLines.length === 0) {
      message.error(t('validation_at_least_one_line'))
      return
    }

    const payload = {
      purchase_order_id: selectedPoId,
      receipt_date: fmtDate(values.receipt_date),
      delivery_note_no: values.delivery_note_no || null,
      remarks: values.remarks || null,
      lines: filledLines.map((l) => ({
        purchase_order_line_id: l.purchase_order_line_id,
        qty_received: l.qty_received,
        unit_cost: l.unit_cost,
        batch_no: l.batch_no || undefined,
        expiry_date: fmtDate(l.expiry_date) || undefined,
        remarks: l.remarks || undefined,
      })),
    }

    try {
      const res = await axiosInstance.post('/goods-receipts', payload)
      message.success(t('messages.created', { docNo: res.data.document_no }))
      navigate(`/purchase/goods-receipts/${res.data.id}`)
    } catch (err: unknown) {
      const errData = (err as { response?: { data?: { message?: string; error_code?: string } } })
        ?.response?.data
      const code = errData?.error_code
      const localized =
        code && t(`errors.${code}`, { defaultValue: '' })
          ? t(`errors.${code}`)
          : null
      message.error(localized ?? errData?.message ?? t('messages.createFailed'))
    }
  }

  return (
    <Card title={t('create')}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <ProFormSelect
          label={t('select_po')}
          placeholder={t('select_po_placeholder')}
          options={poOptions}
          fieldProps={{
            value: selectedPoId ?? undefined,
            showSearch: true,
            filterOption: (input, option) =>
              String(option?.label ?? '').toLowerCase().includes(input.toLowerCase()),
            onChange: (v) => setSelectedPoId((v as number) ?? null),
          }}
          width="lg"
        />

        {poLoading ? (
          <Skeleton active />
        ) : po ? (
          <ProForm
            initialValues={{
              receipt_date: dayjs(),
              delivery_note_no: '',
              remarks: '',
            }}
            onFinish={handleSubmit}
            onReset={() => navigate('/purchase/goods-receipts')}
            submitter={{
              searchConfig: {
                submitText: t('create'),
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
                  <span>
                    {t('purchase_order')}: <strong>{po.document_no}</strong>
                  </span>
                  <Tag color={po.status === 'CONFIRMED' ? 'blue' : 'orange'}>
                    {po.status.replace(/_/g, ' ')}
                  </Tag>
                  <span>
                    {t('warehouse')}: #{po.warehouse_id}
                  </span>
                </Space>
              }
            />

            {lines.length === 0 ? (
              <Alert type="warning" showIcon message={t('no_lines_to_receive')} />
            ) : (
              <>
                <ProForm.Group>
                  <ProFormDatePicker
                    name="receipt_date"
                    label={t('receipt_date')}
                    rules={[{ required: true }]}
                    width="md"
                  />
                  <ProFormText
                    name="delivery_note_no"
                    label={t('delivery_note_no')}
                    width="md"
                  />
                </ProForm.Group>

                <ProFormTextArea
                  name="remarks"
                  label={t('remarks')}
                  fieldProps={{ rows: 2 }}
                />

                <Card title={t('lines')} size="small" style={{ marginBottom: 24 }}>
                  <EditableProTable<GRLineRow>
                    rowKey="id"
                    editableFormRef={editableFormRef}
                    value={lines}
                    onChange={(v) => setLines(v as GRLineRow[])}
                    columns={lineColumns}
                    editable={{
                      type: 'multiple',
                      editableKeys,
                      onChange: (keys) => setEditableKeys(keys as (string | number)[]),
                      onValuesChange: (_record: GRLineRow, allValues: GRLineRow[]) => {
                        setLines(allValues)
                      },
                      actionRender: () => [],
                    }}
                    recordCreatorProps={false}
                    scroll={{ x: 1300 }}
                    size="small"
                  />
                  <Space size="large" style={{ marginTop: 12, justifyContent: 'flex-end', width: '100%' }}>
                    <Typography.Text type="secondary">
                      {t('totalQty')}: {totalsHint.total.toLocaleString('en-MY', { maximumFractionDigits: 4 })}
                    </Typography.Text>
                    <Typography.Text strong>
                      {t('totalCost')}: {po.currency} {totalsHint.totalCost.toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </Typography.Text>
                  </Space>
                </Card>
              </>
            )}
          </ProForm>
        ) : (
          <Alert
            type="info"
            showIcon
            message={t('validation_select_po_first')}
          />
        )}
      </Space>
    </Card>
  )
}
