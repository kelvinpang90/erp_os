/**
 * Minimal edit page — only header fields (remarks / expected_arrival_date).
 * Re-arranging lines on a DRAFT is rare; if needed, cancel the draft and
 * recreate. This keeps the W13 surface small and avoids re-implementing the
 * full multi-row create form.
 */
import { ProForm, ProFormDatePicker, ProFormTextArea } from '@ant-design/pro-components'
import { App, Card, Skeleton } from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { axiosInstance } from '../../api/client'

interface TransferDetail {
  id: number
  status: string
  expected_arrival_date?: string
  remarks?: string
}

export default function TransferEditPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useTranslation('stock_transfer')
  const [transfer, setTransfer] = useState<TransferDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!id) return
    axiosInstance
      .get(`/stock-transfers/${id}`)
      .then((res) => {
        if (res.data.status !== 'DRAFT') {
          message.error(t('messages.only_draft_editable'))
          navigate(`/inventory/transfers/${id}`)
          return
        }
        setTransfer(res.data)
      })
      .catch(() => navigate('/inventory/transfers'))
      .finally(() => setLoading(false))
  }, [id, navigate, message, t])

  const onSubmit = async (values: { expected_arrival_date?: string; remarks?: string }) => {
    if (!id) return false
    setSubmitting(true)
    try {
      await axiosInstance.patch(`/stock-transfers/${id}`, {
        expected_arrival_date: values.expected_arrival_date,
        remarks: values.remarks,
      })
      message.success(t('edit'))
      navigate(`/inventory/transfers/${id}`)
      return true
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? t('messages.update_failed'))
      return false
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <Skeleton active />
  if (!transfer) return null

  return (
    <Card title={t('edit')}>
      <ProForm
        layout="horizontal"
        labelCol={{ span: 6 }}
        wrapperCol={{ span: 14 }}
        initialValues={{
          expected_arrival_date: transfer.expected_arrival_date,
          remarks: transfer.remarks,
        }}
        submitter={{
          searchConfig: { resetText: t('cancel'), submitText: t('edit') },
          submitButtonProps: { loading: submitting },
        }}
        onFinish={onSubmit}
      >
        <ProFormDatePicker
          name="expected_arrival_date"
          label={t('expected_arrival_date')}
        />
        <ProFormTextArea name="remarks" label={t('remarks')} fieldProps={{ rows: 3 }} />
      </ProForm>
    </Card>
  )
}
