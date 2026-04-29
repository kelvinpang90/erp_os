import { Button, message } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
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

export default function InvoiceListPage() {
  const navigate = useNavigate()
  const [scanLoading, setScanLoading] = useState(false)

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

  return (
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
          key="scan"
          icon={<ThunderboltOutlined />}
          loading={scanLoading}
          onClick={handleFinalizeScan}
        >
          Run Finalize Scan
        </Button>,
      ]}
    />
  )
}
