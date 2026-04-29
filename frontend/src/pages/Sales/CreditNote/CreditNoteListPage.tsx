import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../../api/client'
import ResourceListPage from '../../../components/ResourceListPage'
import { creditNoteColumns, type CreditNoteRow } from './CreditNoteColumns'

async function fetchCreditNotes(params: {
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
  const res = await axiosInstance.get(`/credit-notes?${query}`)
  return res.data
}

export default function CreditNoteListPage() {
  const navigate = useNavigate()

  return (
    <ResourceListPage<CreditNoteRow>
      title="Credit Notes"
      columns={[
        ...creditNoteColumns,
        {
          title: 'Action',
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a
              key="view"
              onClick={() => navigate(`/sales/credit-notes/${row.id}`)}
            >
              View
            </a>,
            row.invoice_id ? (
              <a
                key="invoice"
                onClick={() => navigate(`/sales/einvoice/${row.invoice_id}`)}
              >
                Invoice
              </a>
            ) : null,
          ].filter(Boolean) as React.ReactNode[],
        },
      ]}
      fetchData={fetchCreditNotes}
    />
  )
}
