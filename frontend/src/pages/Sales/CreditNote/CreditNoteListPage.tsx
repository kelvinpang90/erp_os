import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../../api/client'
import ResourceListPage from '../../../components/ResourceListPage'
import { getCreditNoteColumns, type CreditNoteRow } from './CreditNoteColumns'

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
  const { t } = useTranslation(['einvoice', 'common'])

  return (
    <ResourceListPage<CreditNoteRow>
      title={t('einvoice:creditNote.listTitle')}
      columns={[
        ...getCreditNoteColumns((key, opts) =>
          t(`einvoice:${key}`, (opts ?? {}) as never) as string,
        ),
        {
          title: t('common:actions'),
          valueType: 'option',
          fixed: 'right',
          width: 120,
          render: (_, row) => [
            <a
              key="view"
              onClick={() => navigate(`/sales/credit-notes/${row.id}`)}
            >
              {t('einvoice:buttons.view')}
            </a>,
            row.invoice_id ? (
              <a
                key="invoice"
                onClick={() => navigate(`/sales/einvoice/${row.invoice_id}`)}
              >
                {t('einvoice:buttons.invoice')}
              </a>
            ) : null,
          ].filter(Boolean) as React.ReactNode[],
        },
      ]}
      fetchData={fetchCreditNotes}
    />
  )
}
