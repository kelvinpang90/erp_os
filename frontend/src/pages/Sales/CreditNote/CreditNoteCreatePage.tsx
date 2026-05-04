import { ArrowLeftOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { axiosInstance } from '../../../api/client'
import { cnReasonLabel } from './CreditNoteColumns'

interface InvoiceLine {
  id: number
  line_no: number
  sku_id: number
  sku_code?: string
  sku_name?: string
  description: string
  qty: string
  unit_price_excl_tax: string
  tax_rate_percent: string
  line_total_incl_tax: string
}

interface InvoiceDetail {
  id: number
  document_no: string
  status: string
  customer_id: number
  customer_name?: string
  currency: string
  warehouse_id?: number
  warehouse_name?: string
  lines: InvoiceLine[]
}

const REASONS = [
  'RETURN',
  'DISCOUNT_ADJUSTMENT',
  'PRICE_CORRECTION',
  'WRITE_OFF',
  'OTHER',
] as const

export default function CreditNoteCreatePage() {
  const [params] = useSearchParams()
  const invoiceId = params.get('invoice_id')
  const navigate = useNavigate()
  const { t } = useTranslation(['einvoice', 'common'])
  const tEinvoice = (key: string, opts?: Record<string, unknown>) =>
    t(`einvoice:${key}`, (opts ?? {}) as never) as unknown as string
  const [form] = Form.useForm()
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [qtyMap, setQtyMap] = useState<Record<number, string>>({})

  useEffect(() => {
    if (!invoiceId) {
      navigate('/sales/credit-notes')
      return
    }
    setLoading(true)
    axiosInstance
      .get(`/invoices/${invoiceId}`)
      .then((res) => {
        const inv = res.data as InvoiceDetail
        setInvoice(inv)
        // Default qty = 0 for every line — user opts in line-by-line.
        const init: Record<number, string> = {}
        inv.lines.forEach((ln) => {
          init[ln.id] = '0'
        })
        setQtyMap(init)
      })
      .catch(() => navigate('/sales/credit-notes'))
      .finally(() => setLoading(false))
  }, [invoiceId, navigate])

  const totalReturned = useMemo(() => {
    if (!invoice) return 0
    let sum = 0
    invoice.lines.forEach((ln) => {
      const q = parseFloat(qtyMap[ln.id] ?? '0')
      const unit = parseFloat(ln.unit_price_excl_tax)
      const taxRate = parseFloat(ln.tax_rate_percent)
      if (!isNaN(q) && q > 0) {
        const excl = q * unit
        sum += excl * (1 + taxRate / 100)
      }
    })
    return sum
  }, [invoice, qtyMap])

  const handleSubmit = async (values: { reason: string; reason_description?: string; remarks?: string }) => {
    if (!invoice) return
    const lines = invoice.lines
      .map((ln) => {
        const q = parseFloat(qtyMap[ln.id] ?? '0')
        return q > 0
          ? { invoice_line_id: ln.id, qty: String(q) }
          : null
      })
      .filter(Boolean) as Array<{ invoice_line_id: number; qty: string }>

    if (lines.length === 0) {
      message.warning(t('einvoice:creditNote.messages.atLeastOneLine'))
      return
    }

    setSubmitting(true)
    try {
      const res = await axiosInstance.post('/credit-notes', {
        invoice_id: invoice.id,
        reason: values.reason,
        reason_description: values.reason_description,
        remarks: values.remarks,
        lines,
      })
      message.success(t('einvoice:creditNote.messages.created', { docNo: res.data?.document_no }))
      navigate(`/sales/credit-notes/${res.data?.id}`)
    } catch (err: unknown) {
      const data = (
        err as {
          response?: {
            data?: {
              message?: string
              detail?: { errors?: { msg?: string; loc?: (string | number)[] }[] }
            }
          }
        }
      )?.response?.data
      const fieldErrors = data?.detail?.errors
        ?.map((e) => `${(e.loc ?? []).filter((p) => p !== 'body').join('.')}: ${e.msg ?? ''}`)
        .filter(Boolean)
        .join('; ')
      message.error(fieldErrors || data?.message || t('einvoice:creditNote.messages.createFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <Spin
        size="large"
        style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }}
      />
    )
  }
  if (!invoice) return null

  const isCreditable =
    invoice.status === 'VALIDATED' || invoice.status === 'FINAL'

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              type="text"
              onClick={() => navigate(`/sales/einvoice/${invoice.id}`)}
            />
            <Typography.Text strong>
              {t('einvoice:creditNote.titleFor', { docNo: invoice.document_no })}
            </Typography.Text>
            <Tag>{invoice.customer_name || `#${invoice.customer_id}`}</Tag>
          </Space>
        }
      >
        {!isCreditable && (
          <Alert
            type="warning"
            showIcon
            message={t('einvoice:creditNote.notCreditable', { status: invoice.status })}
          />
        )}

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{ reason: 'RETURN' }}
          disabled={!isCreditable}
        >
          <Form.Item
            label={t('einvoice:creditNote.fields.reason')}
            name="reason"
            rules={[{ required: true }]}
          >
            <Select
              options={REASONS.map((r) => ({
                value: r,
                label: cnReasonLabel(tEinvoice, r),
              }))}
              style={{ maxWidth: 280 }}
            />
          </Form.Item>
          <Form.Item label={t('einvoice:creditNote.fields.reasonDetail')} name="reason_description">
            <Input.TextArea
              rows={2}
              maxLength={500}
              showCount
              placeholder={t('einvoice:creditNote.placeholders.reasonDescription')}
            />
          </Form.Item>
          <Form.Item label={t('einvoice:remarks')} name="remarks">
            <Input.TextArea rows={2} placeholder={t('einvoice:creditNote.placeholders.remarks')} />
          </Form.Item>

          <Card
            size="small"
            title={t('einvoice:creditNote.linesToCredit')}
            style={{ marginBottom: 16 }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr
                  style={{
                    borderBottom: '1px solid #eee',
                    background: '#fafafa',
                  }}
                >
                  <th style={{ padding: 8, width: 50 }}>#</th>
                  <th style={{ padding: 8 }}>{t('einvoice:creditNote.columns.skuDesc')}</th>
                  <th style={{ padding: 8, width: 90, textAlign: 'right' }}>
                    {t('einvoice:creditNote.columns.invoiced')}
                  </th>
                  <th style={{ padding: 8, width: 100, textAlign: 'right' }}>
                    {t('einvoice:columns.unitPrice')}
                  </th>
                  <th style={{ padding: 8, width: 70, textAlign: 'right' }}>
                    {t('einvoice:columns.taxPct')}
                  </th>
                  <th style={{ padding: 8, width: 140 }}>{t('einvoice:creditNote.columns.returnQty')}</th>
                </tr>
              </thead>
              <tbody>
                {invoice.lines.map((ln) => {
                  const invoiced = parseFloat(ln.qty)
                  return (
                    <tr
                      key={ln.id}
                      style={{ borderBottom: '1px solid #f5f5f5' }}
                    >
                      <td style={{ padding: 8 }}>{ln.line_no}</td>
                      <td style={{ padding: 8 }}>
                        <div>
                          {ln.sku_code
                            ? `${ln.sku_code} — ${ln.sku_name}`
                            : '-'}
                        </div>
                        <div style={{ color: '#888', fontSize: 12 }}>
                          {ln.description}
                        </div>
                      </td>
                      <td
                        style={{ padding: 8, textAlign: 'right' }}
                      >{invoiced}</td>
                      <td
                        style={{ padding: 8, textAlign: 'right' }}
                      >{ln.unit_price_excl_tax}</td>
                      <td
                        style={{ padding: 8, textAlign: 'right' }}
                      >{ln.tax_rate_percent}</td>
                      <td style={{ padding: 8 }}>
                        <InputNumber
                          min={0}
                          max={invoiced}
                          step={0.01}
                          value={parseFloat(qtyMap[ln.id] ?? '0')}
                          onChange={(v) =>
                            setQtyMap((m) => ({
                              ...m,
                              [ln.id]: String(v ?? 0),
                            }))
                          }
                          style={{ width: '100%' }}
                        />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            <div
              style={{
                marginTop: 12,
                textAlign: 'right',
                fontWeight: 600,
              }}
            >
              {t('einvoice:creditNote.totalCredit')}:{' '}
              {invoice.currency}{' '}
              {totalReturned.toLocaleString('en-MY', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </div>
          </Card>

          <Space>
            <Button onClick={() => navigate(-1)}>{t('common:back')}</Button>
            <Button type="primary" htmlType="submit" loading={submitting}>
              {t('einvoice:creditNote.buttons.createDraft')}
            </Button>
          </Space>
        </Form>
      </Card>
    </Space>
  )
}
