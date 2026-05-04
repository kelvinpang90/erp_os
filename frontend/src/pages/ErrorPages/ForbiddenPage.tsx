import { Button, Result } from 'antd'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

export default function ForbiddenPage() {
  const navigate = useNavigate()
  const { t } = useTranslation('common')
  return (
    <Result
      status="403"
      title="403"
      subTitle={t('errorPages.forbidden')}
      extra={
        <Button type="primary" onClick={() => navigate('/')}>
          {t('errorPages.backHome')}
        </Button>
      }
    />
  )
}
