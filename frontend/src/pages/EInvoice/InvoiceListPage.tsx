import { Button, InputNumber, Modal, Space, Typography, message } from 'antd'
import { CalendarOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { getInvoiceColumns, type InvoiceRow } from './InvoiceColumns'

async function fetchInvoices(params: {
  current?: number
  pageSize?: number
  document_no?: string
  status?: string
}) {
  const { current = 1, pageSize = 20, document_no, status } = params
  const query = new URLSearchParams({
    page: String(current),
    page_size: String(pageSize),
  })
  if (document_no) query.set('search', document_no)
  if (status) query.set('status', status)
  const res = await axiosInstance.get(`/invoices?${query}`)
  return res.data
}

function previousMonth(): { year: number; month: number } {
  const today = new Date()
  // Default to the most recently completed month.
  const d = new Date(today.getFullYear(), today.getMonth() - 1, 1)
  return { year: d.getFullYear(), month: d.getMonth() + 1 }
}

export default function InvoiceListPage() {
  const navigate = useNavigate()
  const { t } = useTranslation(['einvoice', 'common'])
  const [scanLoading, setScanLoading] = useState(false)
  const [consOpen, setConsOpen] = useState(false)
  const [consLoading, setConsLoading] = useState(false)
  const [consYear, setConsYear] = useState(previousMonth().year)
  const [consMonth, setConsMonth] = useState(previousMonth().month)

  const handleFinalizeScan = async () => {
    setScanLoading(true)
    try {
      const res = await axiosInstance.post('/invoices/admin/run-finalize-scan')
      const { finalized_count, finalize_window_seconds } = res.data
      message.success(
        t('einvoice:messages.finalizeScanComplete', {
          count: finalized_count,
          seconds: finalize_window_seconds,
        }),
      )
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        t('einvoice:messages.finalizeScanFailed')
      message.error(msg)
    } finally {
      setScanLoading(false)
    }
  }

  const handleGenerateConsolidated = async () => {
    setConsLoading(true)
    try {
      const res = await axiosInstance.post(
        '/invoices/admin/generate-monthly-consolidated',
        { year: consYear, month: consMonth },
      )
      const { generated_count, customer_ids } = res.data
      const monthStr = `${consYear}-${String(consMonth).padStart(2, '0')}`
      if (generated_count === 0) {
        message.info(t('einvoice:messages.consolidatedNoneFound', { month: monthStr }))
      } else {
        message.success(
          t('einvoice:messages.consolidatedGenerated', {
            count: generated_count,
            customers: customer_ids.length,
            month: monthStr,
          }),
        )
      }
      setConsOpen(false)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        t('einvoice:messages.consolidatedFailed')
      message.error(msg)
    } finally {
      setConsLoading(false)
    }
  }

  return (
    <>
      <ResourceListPage<InvoiceRow>
        title={t('einvoice:title')}
        columns={[
          ...getInvoiceColumns((key, opts) =>
            t(`einvoice:${key}`, (opts ?? {}) as never) as string,
          ),
          {
            title: t('common:actions'),
            valueType: 'option',
            fixed: 'right',
            width: 120,
            render: (_, row) => [
              <a key="view" onClick={() => navigate(`/sales/einvoice/${row.id}`)}>
                {t('einvoice:buttons.view')}
              </a>,
              row.sales_order_id ? (
                <a key="so" onClick={() => navigate(`/sales/orders/${row.sales_order_id}`)}>
                  {t('einvoice:buttons.so')}
                </a>
              ) : null,
            ].filter(Boolean) as React.ReactNode[],
          },
        ]}
        fetchData={fetchInvoices}
        toolbarActions={[
          <Button
            key="cons"
            icon={<CalendarOutlined />}
            onClick={() => setConsOpen(true)}
          >
            {t('einvoice:buttons.generateMonthlyConsolidated')}
          </Button>,
          <Button
            key="scan"
            icon={<ThunderboltOutlined />}
            loading={scanLoading}
            onClick={handleFinalizeScan}
          >
            {t('einvoice:run_finalize_scan')}
          </Button>,
        ]}
      />

      <Modal
        title={t('einvoice:consolidated.modalTitle')}
        open={consOpen}
        onCancel={() => setConsOpen(false)}
        onOk={handleGenerateConsolidated}
        confirmLoading={consLoading}
        okText={t('einvoice:consolidated.okText')}
      >
        <Typography.Paragraph>
          {t('einvoice:consolidated.description')}
        </Typography.Paragraph>
        <Space>
          <span>{t('einvoice:consolidated.year')}:</span>
          <InputNumber
            min={2024}
            max={2100}
            value={consYear}
            onChange={(v) => setConsYear(Number(v ?? consYear))}
          />
          <span>{t('einvoice:consolidated.month')}:</span>
          <InputNumber
            min={1}
            max={12}
            value={consMonth}
            onChange={(v) => setConsMonth(Number(v ?? consMonth))}
          />
        </Space>
      </Modal>
    </>
  )
}
