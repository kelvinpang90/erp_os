import {
  EditableProTable,
  ProForm,
  ProFormDatePicker,
  ProFormSelect,
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

  const warehouseOptions = warehouses.map((w) => ({ value: w.id, label: w.name }))

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
    {
      title: t('actions'),
      valueType: 'option',
      width: 100,
      render: (_, row, _idx, action) => [
        <a key="edit" onClick={() => action?.startEditable?.(row.id)}>
          {t('edit')}
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
    const validLines = lines.filter(
      (l) => l.sku_id && l.uom_id && l.qty_sent !== undefined && Number(l.qty_sent) > 0,
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
          uom_id: l.uom_id!,
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
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? 'Failed to create transfer')
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

      <Card title={t('lines')}>
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
        <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
          {t('summary')}: {lines.length} line(s)
        </Typography.Paragraph>
      </Card>
    </Space>
  )
}
