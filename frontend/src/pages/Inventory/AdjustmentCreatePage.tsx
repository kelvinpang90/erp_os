import { PlusOutlined } from '@ant-design/icons'
import {
  EditableProTable,
  ProForm,
  ProFormDatePicker,
  ProFormSelect,
  ProFormText,
  ProFormTextArea,
  type EditableFormInstance,
  type ProColumns,
  type ProFormInstance,
} from '@ant-design/pro-components'
import { App, Button, Card, Space, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface SkuOption {
  id: number
  code: string
  name: string
  // Backend SKUResponse exposes the unit-of-measure as `base_uom_id`.
  base_uom_id: number
}

interface WarehouseOption {
  id: number
  name: string
}

interface LineRow {
  id: string
  sku_id?: number
  uom_id?: number
  qty_before?: number
  qty_after?: number
  unit_cost?: number
  batch_no?: string
  notes?: string
}

let _seq = 0
const newRowKey = () => `tmp_${++_seq}`

const REASON_KEYS = [
  'PHYSICAL_COUNT',
  'DAMAGE',
  'THEFT',
  'CORRECTION',
  'EXPIRY',
  'OTHER',
] as const

export default function AdjustmentCreatePage() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation('stock_adjustment')

  const [warehouses, setWarehouses] = useState<WarehouseOption[]>([])
  const [skus, setSkus] = useState<SkuOption[]>([])
  const [lines, setLines] = useState<LineRow[]>([])
  const [editableKeys, setEditableKeys] = useState<(string | number)[]>([])
  const [submitting, setSubmitting] = useState(false)
  const editableFormRef = useRef<EditableFormInstance<LineRow>>()
  const formRef = useRef<ProFormInstance>()

  useEffect(() => {
    // allSettled + page_size=100 (backend cap) — see TransferCreatePage for the
    // postmortem on why Promise.all + page_size=200 blanked both dropdowns.
    Promise.allSettled([
      axiosInstance.get('/warehouses?page_size=100'),
      axiosInstance.get('/skus?page_size=100'),
    ]).then(([wh, sk]) => {
      let anyFailed = false
      if (wh.status === 'fulfilled') setWarehouses(wh.value.data.items)
      else anyFailed = true
      if (sk.status === 'fulfilled') setSkus(sk.value.data.items)
      else anyFailed = true
      if (anyFailed) message.warning('Some reference data failed to load. Please refresh if dropdowns are empty.')
    })
  }, [message])

  const skuOptions = skus.map((s) => ({
    value: s.id,
    label: `${s.code} — ${s.name}`,
  }))

  const lineColumns: ProColumns<LineRow>[] = [
    {
      title: t('sku'),
      dataIndex: 'sku_id',
      valueType: 'select',
      // SKU onChange is row-scoped via the `rowKey` from the config closure
      // (NOT rowIndex — that's unstable across add/delete). On select we
      // fetch the current on-hand from /api/inventory/stocks and write it
      // into qty_before so the user only enters the physical-count qty_after.
      fieldProps: (_form, config) => ({
        options: skuOptions,
        showSearch: true,
        filterOption: (input: string, option?: { label?: string }) =>
          (option?.label ?? '').toLowerCase().includes(input.toLowerCase()),
        onChange: async (val: number) => {
          const rowKey = (config as { rowKey?: string | number } | undefined)?.rowKey
          const wh = formRef.current?.getFieldValue('warehouse_id') as number | undefined
          if (!val || !wh || rowKey === undefined) return
          try {
            const res = await axiosInstance.get(
              `/inventory/stocks?sku_id=${val}&warehouse_id=${wh}`,
            )
            const onHand = parseFloat(res.data.on_hand) || 0
            // Write into the editable row's form so the input visibly updates.
            editableFormRef.current?.setRowData?.(rowKey, { qty_before: onHand })
          } catch {
            // Network/permission glitch — leave qty_before blank, user can type.
          }
        },
      }),
      formItemProps: { rules: [{ required: true }] },
      width: 280,
    },
    {
      title: t('qty_before'),
      dataIndex: 'qty_before',
      valueType: 'digit',
      fieldProps: { min: 0, step: 1 },
      formItemProps: { rules: [{ required: true }] },
      width: 110,
    },
    {
      title: t('qty_after'),
      dataIndex: 'qty_after',
      valueType: 'digit',
      fieldProps: { min: 0, step: 1 },
      formItemProps: { rules: [{ required: true }] },
      width: 110,
    },
    {
      title: t('qty_diff'),
      width: 100,
      align: 'right' as const,
      editable: false,
      render: (_, row) => {
        if (row.qty_before === undefined || row.qty_after === undefined) return '—'
        const diff = Number(row.qty_after) - Number(row.qty_before)
        const color = diff > 0 ? '#52c41a' : diff < 0 ? '#ff4d4f' : undefined
        return <span style={{ color }}>{diff > 0 ? `+${diff}` : diff}</span>
      },
    },
    {
      title: t('unit_cost'),
      dataIndex: 'unit_cost',
      valueType: 'digit',
      fieldProps: { min: 0, step: 0.01 },
      tooltip: t('unit_cost_hint'),
      width: 130,
    },
    { title: t('batch_no'), dataIndex: 'batch_no', width: 110 },
    { title: t('notes'), dataIndex: 'notes', width: 200, ellipsis: true },
    // Delete action is rendered via editable.actionRender (not a column) —
    // see TransferCreatePage for the reason.
  ]

  const handleAddLine = () => {
    const id = newRowKey()
    setLines((prev) => [...prev, { id }])
    setEditableKeys((prev) => [...prev, id])
  }

  /**
   * Re-fetch on_hand for every existing line when the warehouse changes,
   * so a SKU's qty_before always reflects the *currently selected* warehouse.
   * Lines with no SKU yet are skipped; failures are silent (the user can
   * still type qty_before manually).
   */
  const refreshAllQtyBefore = async (warehouseId: number) => {
    for (const l of lines) {
      const live = editableFormRef.current?.getRowData?.(l.id)
      const skuId = (live?.sku_id ?? l.sku_id) as number | undefined
      if (!skuId) continue
      try {
        const res = await axiosInstance.get(
          `/inventory/stocks?sku_id=${skuId}&warehouse_id=${warehouseId}`,
        )
        const onHand = parseFloat(res.data.on_hand) || 0
        editableFormRef.current?.setRowData?.(l.id, { qty_before: onHand })
      } catch {
        // ignore — leave the row's qty_before untouched
      }
    }
  }

  const onSubmit = async (values: {
    warehouse_id: number
    business_date: string
    reason: string
    reason_description?: string
    remarks?: string
  }) => {
    // Read live form values per row — EditableProTable's onValuesChange
    // isn't reliably synchronous with parent state.
    const liveRows: LineRow[] = lines.map((l) => {
      const live = editableFormRef.current?.getRowData?.(l.id)
      return live ? { ...l, ...live, id: l.id } : l
    })
    // uom_id resolved via sku_id lookup (form may not carry it).
    const skuById = new Map(skus.map((s) => [s.id, s]))
    const validLines = liveRows.filter(
      (l) =>
        l.sku_id &&
        l.qty_before !== undefined &&
        l.qty_after !== undefined,
    )
    if (validLines.length === 0) {
      message.error(t('no_lines_error'))
      return false
    }

    setSubmitting(true)
    try {
      const payload = {
        warehouse_id: values.warehouse_id,
        business_date: values.business_date,
        reason: values.reason,
        reason_description: values.reason_description,
        remarks: values.remarks,
        lines: validLines.map((l) => ({
          sku_id: l.sku_id!,
          uom_id: skuById.get(l.sku_id!)?.base_uom_id ?? l.uom_id!,
          qty_before: l.qty_before!,
          qty_after: l.qty_after!,
          unit_cost: l.unit_cost,
          batch_no: l.batch_no || undefined,
          notes: l.notes || undefined,
        })),
      }
      const res = await axiosInstance.post('/stock-adjustments', payload)
      message.success(t('create'))
      navigate(`/inventory/adjustments/${res.data.id}`)
      return true
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { message?: string; detail?: unknown } } })?.response?.data
      const errors = (data?.detail as { errors?: Array<{ loc: unknown[]; msg: string }> } | undefined)?.errors
      if (errors && errors.length > 0) {
        const first = errors[0]
        message.error(`${data?.message ?? 'Validation failed'} — ${first.loc.join('.')}: ${first.msg}`)
      } else {
        message.error(data?.message ?? 'Failed to create adjustment')
      }
      // eslint-disable-next-line no-console
      console.error('[AdjustmentCreate] submit failed', { payload, response: data })
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card title={t('create')}>
        <ProForm
          formRef={formRef}
          layout="horizontal"
          labelCol={{ span: 6 }}
          wrapperCol={{ span: 14 }}
          // Submit button is rendered at the bottom of the page (after Lines)
          // instead of inside the form card.
          submitter={false}
          initialValues={{ business_date: dayjs().format('YYYY-MM-DD') }}
          onFinish={onSubmit}
          // When warehouse changes, re-fetch on_hand for every existing line so
          // qty_before reflects the *new* warehouse's book value, not the
          // stale one from the previously selected warehouse.
          onValuesChange={(changed) => {
            if (changed.warehouse_id !== undefined) {
              void refreshAllQtyBefore(changed.warehouse_id as number)
            }
          }}
        >
          <ProFormSelect
            name="warehouse_id"
            label={t('warehouse')}
            options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
            rules={[{ required: true }]}
          />
          <ProFormDatePicker
            name="business_date"
            label={t('business_date')}
            rules={[{ required: true }]}
          />
          <ProFormSelect
            name="reason"
            label={t('reason')}
            options={REASON_KEYS.map((k) => ({ value: k, label: t(`reason_${k}`) }))}
            rules={[{ required: true }]}
          />
          <ProFormText name="reason_description" label={t('reason_description')} />
          <ProFormTextArea
            name="remarks"
            label={t('remarks')}
            fieldProps={{ rows: 2 }}
          />
        </ProForm>
      </Card>

      <Card
        title={t('lines')}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAddLine}>
            {t('add_line')}
          </Button>
        }
      >
        <Typography.Paragraph type="secondary">
          {t('manager_only_warning')}
        </Typography.Paragraph>
        <EditableProTable<LineRow>
          rowKey="id"
          value={lines}
          onChange={(v) => setLines(v as LineRow[])}
          columns={lineColumns}
          editableFormRef={editableFormRef}
          // recordCreatorProps disabled — rows are added via the explicit
          // "+ Add Line" button so they enter `lines` immediately and
          // onValuesChange can mutate an existing row, not a phantom one.
          recordCreatorProps={false}
          editable={{
            type: 'multiple',
            editableKeys,
            onChange: (keys) => setEditableKeys(keys as (string | number)[]),
            onValuesChange: (_record, allValues) => setLines(allValues as LineRow[]),
            actionRender: (row) => [
              <a
                key="delete"
                onClick={() => {
                  setLines((prev) => prev.filter((l) => l.id !== row.id))
                  setEditableKeys((prev) => prev.filter((k) => k !== row.id))
                }}
              >
                {t('delete', { ns: 'common', defaultValue: 'Delete' })}
              </a>,
            ],
          }}
        />
      </Card>

      <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '16px 0' }}>
        <Button
          type="primary"
          size="large"
          loading={submitting}
          onClick={() => formRef.current?.submit()}
        >
          {t('create')}
        </Button>
      </div>
    </Space>
  )
}
