import { Button, InputNumber, Modal, Space, Typography, message } from 'antd'
import { CalendarOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/client'
import ResourceListPage from '../../components/ResourceListPage'
import { invoiceColumns, type InvoiceRow } from './InvoiceColumns'

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
        `Finalize scan complete: ${finalized_count} invoice(s) advanced to FINAL ` +
          `(window = ${finalize_window_seconds}s).`,
      )
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        'Failed to run finalize scan.'
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
      if (generated_count === 0) {
        message.info(
          `No eligible B2C sales orders found for ${consYear}-${String(consMonth).padStart(2, '0')}.`,
        )
      } else {
        message.success(
          `Generated ${generated_count} Consolidated Invoice(s) covering ` +
            `${customer_ids.length} customer(s) for ${consYear}-${String(consMonth).padStart(2, '0')}.`,
        )
      }
      setConsOpen(false)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        'Failed to generate consolidated invoices.'
      message.error(msg)
    } finally {
      setConsLoading(false)
    }
  }

  return (
    <>
      <ResourceListPage<InvoiceRow>
        title="e-Invoices"
        columns={[
          ...invoiceColumns,
          {
            title: 'Action',
            valueType: 'option',
            fixed: 'right',
            width: 120,
            render: (_, row) => [
              <a key="view" onClick={() => navigate(`/sales/einvoice/${row.id}`)}>
                View
              </a>,
              row.sales_order_id ? (
                <a key="so" onClick={() => navigate(`/sales/orders/${row.sales_order_id}`)}>
                  SO
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
            Generate Monthly Consolidated
          </Button>,
          <Button
            key="scan"
            icon={<ThunderboltOutlined />}
            loading={scanLoading}
            onClick={handleFinalizeScan}
          >
            Run Finalize Scan
          </Button>,
        ]}
      />

      <Modal
        title="Generate Monthly Consolidated B2C Invoices"
        open={consOpen}
        onCancel={() => setConsOpen(false)}
        onOk={handleGenerateConsolidated}
        confirmLoading={consLoading}
        okText="Generate"
      >
        <Typography.Paragraph>
          Roll up every B2C customer's shipped Sales Orders for the chosen month
          into one Draft Consolidated Invoice each. SOs already individually
          invoiced or already rolled-up are skipped automatically.
        </Typography.Paragraph>
        <Space>
          <span>Year:</span>
          <InputNumber
            min={2024}
            max={2100}
            value={consYear}
            onChange={(v) => setConsYear(Number(v ?? consYear))}
          />
          <span>Month:</span>
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
