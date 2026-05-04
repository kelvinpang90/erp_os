import { Button, Result } from 'antd'
import { useTranslation } from 'react-i18next'

interface Props {
  onRetry?: () => void
}

export default function ServerErrorPage({ onRetry }: Props) {
  const { t } = useTranslation('common')
  return (
    <Result
      status="500"
      title="500"
      subTitle={t('errorPages.serverError')}
      extra={
        <Button type="primary" onClick={onRetry ?? (() => window.location.reload())}>
          {t('errorPages.retry')}
        </Button>
      }
    />
  )
}
