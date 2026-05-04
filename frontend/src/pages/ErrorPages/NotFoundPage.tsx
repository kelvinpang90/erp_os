import { Button, Result } from 'antd'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

export default function NotFoundPage() {
  const navigate = useNavigate()
  const { t } = useTranslation('common')
  return (
    <Result
      status="404"
      title="404"
      subTitle={t('errorPages.notFound')}
      extra={
        <Button type="primary" onClick={() => navigate('/')}>
          {t('errorPages.backHome')}
        </Button>
      }
    />
  )
}
