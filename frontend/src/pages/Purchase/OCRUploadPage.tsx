/**
 * OCR Upload page — drop a PO invoice, get a pre-filled PO create form.
 *
 * Flow:
 *   1. User drops file
 *   2. SSEUploader streams progress events (uploaded → calling_ai → parsing → done)
 *   3. On 'done' event we navigate to /purchase/orders/create with the OCR
 *      payload in router state; POEditPage reads `state.ocrPrefill` and applies.
 *   4. On any error, an inline alert shows what failed and a "skip OCR"
 *      button leads to a blank PO form.
 */

import { Button, Card, Space, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import SSEUploader from '../../components/SSEUploader'

// Mirrors backend/app/schemas/ai.py::OCRPurchaseOrder
export interface OCRLineResult {
  description: string
  sku_code: string | null
  qty: string | number
  uom: string | null
  unit_price_excl_tax: string | number
  tax_rate_percent: string | number | null
  discount_percent: string | number | null
}

export interface OCRPurchaseOrderResult {
  supplier_name: string | null
  supplier_tin: string | null
  supplier_address: string | null
  invoice_no: string | null
  business_date: string | null
  currency: string | null
  subtotal_excl_tax: string | number | null
  tax_amount: string | number | null
  total_incl_tax: string | number | null
  lines: OCRLineResult[]
  remarks: string | null
  confidence: 'high' | 'medium' | 'low'
}

const MAX_SIZE_MB = 10

export default function OCRUploadPage() {
  const navigate = useNavigate()
  const { t } = useTranslation('ocr')

  const handleSuccess = (result: OCRPurchaseOrderResult) => {
    // Brief delay so the user sees the "done" stage tick to 100% before nav.
    setTimeout(() => {
      navigate('/purchase/orders/create', { state: { ocrPrefill: result } })
    }, 400)
  }

  const skipToBlankForm = () => {
    navigate('/purchase/orders/create')
  }

  return (
    <Card
      title={
        <Space direction="vertical" size={0}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {t('page_title')}
          </Typography.Title>
          <Typography.Text type="secondary">{t('page_subtitle')}</Typography.Text>
        </Space>
      }
      extra={
        <Button onClick={skipToBlankForm}>{t('manual_fallback_button')}</Button>
      }
    >
      <SSEUploader<OCRPurchaseOrderResult>
        endpoint="/api/ai/ocr/purchase-order"
        accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
        maxSizeMB={MAX_SIZE_MB}
        i18nNs="ocr"
        onSuccess={handleSuccess}
      />
    </Card>
  )
}
