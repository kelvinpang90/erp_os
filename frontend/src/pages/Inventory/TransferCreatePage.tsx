import { PlusOutlined } from '@ant-design/icons'
import {
  EditableProTable,
  ProForm,
  ProFormDatePicker,
  ProFormSelect,
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
  // Naming it `uom_id` on the frontend would silently break the
  // skuById.get(...)?.uom_id lookup at submit time → 422 from the API.
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
  qty_sent?: number
  batch_no?: string
  expiry_date?: string
}

let _seq = 0
const newRowKey = () => `tmp_${++_seq}`

export default function TransferCreatePage() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation('stock_transfer')

  const [warehouses, setWarehouses] = useState<WarehouseOption[]>([])
  const [skus, setSkus] = useState<SkuOption[]>([])
  const [lines, setLines] = useState<LineRow[]>([])
  const [editableKeys, setEditableKeys] = useState<(string | number)[]>([])
  const [submitting, setSubmitting] = useState(false)
  // Used at submit time to read in-progress field values directly from the
  // EditableProTable's form, since onValuesChange isn't always synchronous
  // with our parent `lines` state.
  const editableFormRef = useRef<EditableFormInstance<LineRow>>()
  // Header form ref so the submit button placed at the bottom of the page
  // (outside the form card) can trigger validation + submit.
  const formRef = useRef<ProFormInstance>()

  useEffect(() => {
    // allSettled so one slow / failed call doesn't blank the other dropdown.
    // Backend caps page_size at 100 — sending more triggers a 422 and previously
    // killed BOTH dropdowns under Promise.all.
    Promise.allSettled([
      axiosInstance.get('/warehouses?page_size=100'),
      axiosInstance.get('/skus?page_size=100'),
    ]).then(([wh, sk]) => {
      let anyFailed = false
      if (wh.status === 'fulfilled') setWarehouses(wh.value.data.items)
      else anyFailed = true
      if (sk.status === 'fulfilled') setSkus(sk.value.data.items)
      else anyFailed = true
      if (anyFailed) message.warning(t('messages.ref_data_partial'))
    })
  }, [message, t])

  const skuOptions = skus.map((s) => ({
    value: s.id,
    label: `${s.code} — ${s.name}`,
  }))

  const warehouseOptions = warehouses.map((w) => ({ value: w.id, label: w.name }))

  const lineColumns: ProColumns<LineRow>[] = [
    {
      title: t('sku'),
      dataIndex: 'sku_id',
      valueType: 'select',
      // No row-state side-effects here — uom_id is recovered via sku_id lookup
      // at submit time, so the form can fully own the field's lifecycle. The
      // earlier rowIndex-based setLines clobbered other rows when adding a
      // second line.
      fieldProps: {
        options: skuOptions,
        showSearch: true,
        filterOption: (input: string, option?: { label?: string }) =>
          (option?.label ?? '').toLowerCase().includes(input.toLowerCase()),
      },
      formItemProps: { rules: [{ required: true, message: t('sku') }] },
      width: 280,
    },
    {
      title: t('qty_sent'),
      dataIndex: 'qty_sent',
      valueType: 'digit',
      fieldProps: { min: 0.0001, step: 1 },
      formItemProps: { rules: [{ required: true, message: t('qty_sent') }] },
      width: 110,
    },
    { title: t('batch_no'), dataIndex: 'batch_no', width: 110 },
    { title: t('expiry_date'), dataIndex: 'expiry_date', valueType: 'date', width: 130 },
    // The Delete action lives in `editable.actionRender` instead of a column,
    // because EditableProTable swaps `valueType: 'option'` columns for the
    // editable.actionRender output while a row is in edit mode — a custom
    // render() in the column would never appear for our always-editing rows.
  ]

  const handleAddLine = () => {
    const id = newRowKey()
    setLines((prev) => [...prev, { id }])
    setEditableKeys((prev) => [...prev, id])
  }

  const onSubmit = async (values: {
    from_warehouse_id: number
    to_warehouse_id: number
    business_date: string
    expected_arrival_date?: string
    remarks?: string
  }) => {
    if (values.from_warehouse_id === values.to_warehouse_id) {
      message.error(t('same_warehouse_error'))
      return false
    }
    // Pull live form values for every editable row — EditableProTable's
    // onValuesChange isn't reliably synchronous with our parent state, so
    // reading the row state alone misses fields the user just typed.
    const liveRows: LineRow[] = lines.map((l) => {
      const live = editableFormRef.current?.getRowData?.(l.id)
      return live ? { ...l, ...live, id: l.id } : l
    })
    // uom_id resolved via sku_id lookup (form may not carry it).
    const skuById = new Map(skus.map((s) => [s.id, s]))
    const validLines = liveRows.filter(
      (l) => l.sku_id && l.qty_sent !== undefined && Number(l.qty_sent) > 0,
    )
    if (validLines.length === 0) {
      message.error(t('no_lines_error'))
      return false
    }

    setSubmitting(true)
    try {
      const payload = {
        from_warehouse_id: values.from_warehouse_id,
        to_warehouse_id: values.to_warehouse_id,
        business_date: values.business_date,
        expected_arrival_date: values.expected_arrival_date,
        remarks: values.remarks,
        lines: validLines.map((l) => ({
          sku_id: l.sku_id!,
          uom_id: skuById.get(l.sku_id!)?.base_uom_id ?? l.uom_id!,
          qty_sent: l.qty_sent!,
          batch_no: l.batch_no || undefined,
          expiry_date: l.expiry_date || undefined,
        })),
      }
      const res = await axiosInstance.post('/stock-transfers', payload)
      message.success(t('create'))
      navigate(`/inventory/transfers/${res.data.id}`)
      return true
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { message?: string; detail?: unknown } } })?.response?.data
      // Surface FastAPI 422 field-level errors so the user knows which line/field
      // failed instead of just the generic "Request validation failed".
      const errors = (data?.detail as { errors?: Array<{ loc: unknown[]; msg: string }> } | undefined)?.errors
      if (errors && errors.length > 0) {
        const first = errors[0]
        message.error(`${data?.message ?? t('messages.validation_failed')} — ${first.loc.join('.')}: ${first.msg}`)
      } else {
        message.error(data?.message ?? t('messages.create_failed'))
      }
       
      console.error('[TransferCreate] submit failed', { values, response: data })
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
          // instead of inside the form card, so users can review lines before
          // submitting.
          submitter={false}
          initialValues={{ business_date: dayjs().format('YYYY-MM-DD') }}
          onFinish={onSubmit}
        >
          <ProFormSelect
            name="from_warehouse_id"
            label={t('from_warehouse')}
            options={warehouseOptions}
            rules={[{ required: true }]}
          />
          <ProFormSelect
            name="to_warehouse_id"
            label={t('to_warehouse')}
            options={warehouseOptions}
            rules={[{ required: true }]}
          />
          <ProFormDatePicker
            name="business_date"
            label={t('business_date')}
            rules={[{ required: true }]}
          />
          <ProFormDatePicker
            name="expected_arrival_date"
            label={t('expected_arrival_date')}
          />
          <ProFormTextArea name="remarks" label={t('remarks')} fieldProps={{ rows: 2 }} />
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
        <EditableProTable<LineRow>
          rowKey="id"
          value={lines}
          onChange={(v) => setLines(v as LineRow[])}
          columns={lineColumns}
          editableFormRef={editableFormRef}
          // recordCreatorProps disabled — rows are added via the explicit
          // "+ Add Line" button above so they enter `lines` immediately and
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
        <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
          {t('summary_lines', { count: lines.length })}
        </Typography.Paragraph>
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
