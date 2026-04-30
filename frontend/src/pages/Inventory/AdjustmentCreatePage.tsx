import {
  EditableProTable,
  ProForm,
  ProFormDatePicker,
  ProFormSelect,
  ProFormText,
  ProFormTextArea,
  type ProColumns,
} from '@ant-design/pro-components'
import { App, Card, Space, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface SkuOption {
  id: number
  code: string
  name: string
  uom_id: number
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

  useEffect(() => {
    Promise.all([
      axiosInstance.get('/warehouses?page_size=100'),
      axiosInstance.get('/skus?page_size=200'),
    ])
      .then(([wh, sk]) => {
        setWarehouses(wh.data.items)
        setSkus(sk.data.items)
      })
      .catch(() => message.error('Failed to load reference data.'))
  }, [message])

  const skuOptions = skus.map((s) => ({
    value: s.id,
    label: `${s.code} — ${s.name}`,
    uom_id: s.uom_id,
  }))

  const lineColumns: ProColumns<LineRow>[] = [
    {
      title: t('sku'),
      dataIndex: 'sku_id',
      valueType: 'select',
      fieldProps: (_: unknown, { rowIndex }: { rowIndex: number }) => ({
        options: skuOptions,
        showSearch: true,
        filterOption: (input: string, option?: { label?: string }) =>
          (option?.label ?? '').toLowerCase().includes(input.toLowerCase()),
        onChange: (val: number) => {
          const sku = skus.find((s) => s.id === val)
          if (sku) {
            setLines((prev) => {
              const next = [...prev]
              next[rowIndex] = { ...next[rowIndex], sku_id: val, uom_id: sku.uom_id }
              return next
            })
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
    {
      title: t('actions'),
      valueType: 'option',
      width: 100,
      render: (_, row, _idx, action) => [
        <a key="edit" onClick={() => action?.startEditable?.(row.id)}>
          {t('edit', { defaultValue: 'Edit' })}
        </a>,
        <a
          key="delete"
          onClick={() => setLines((prev) => prev.filter((l) => l.id !== row.id))}
        >
          {t('cancel', { defaultValue: 'Delete' })}
        </a>,
      ],
    },
  ]

  const onSubmit = async (values: {
    warehouse_id: number
    business_date: string
    reason: string
    reason_description?: string
    remarks?: string
  }) => {
    const validLines = lines.filter(
      (l) =>
        l.sku_id &&
        l.uom_id &&
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
          uom_id: l.uom_id!,
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
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? 'Failed to create adjustment')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card title={t('create')}>
        <ProForm
          layout="horizontal"
          labelCol={{ span: 6 }}
          wrapperCol={{ span: 14 }}
          submitter={{
            searchConfig: { resetText: t('cancel'), submitText: t('create') },
            submitButtonProps: { loading: submitting },
          }}
          initialValues={{ business_date: dayjs().format('YYYY-MM-DD') }}
          onFinish={onSubmit}
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

      <Card title={t('lines')}>
        <Typography.Paragraph type="secondary">
          {t('manager_only_warning')}
        </Typography.Paragraph>
        <EditableProTable<LineRow>
          rowKey="id"
          value={lines}
          onChange={(v) => setLines(v as LineRow[])}
          columns={lineColumns}
          recordCreatorProps={{
            position: 'bottom',
            record: () => ({ id: newRowKey() }),
            creatorButtonText: t('add_line'),
          }}
          editable={{
            type: 'multiple',
            editableKeys,
            onChange: (keys) => setEditableKeys(keys as (string | number)[]),
            onValuesChange: (_record, allValues) => setLines(allValues as LineRow[]),
            actionRender: () => [],
          }}
        />
      </Card>
    </Space>
  )
}
