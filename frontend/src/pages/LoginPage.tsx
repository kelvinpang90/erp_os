import {
  AuditOutlined,
  GlobalOutlined,
  LockOutlined,
  RocketOutlined,
  SafetyOutlined,
  ScanOutlined,
  ShoppingCartOutlined,
  ShoppingOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { LoginForm, ProFormText } from '@ant-design/pro-components'
import { App, Card, Grid, Tag, Typography, theme } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../hooks/useAuth'

const { useBreakpoint } = Grid

const DEMO_ACCOUNTS = [
  { key: 'admin', email: 'admin@demo.my', password: 'Admin@123', icon: <SafetyOutlined /> },
  { key: 'manager', email: 'manager@demo.my', password: 'Manager@123', icon: <TeamOutlined /> },
  { key: 'sales', email: 'sales@demo.my', password: 'Sales@123', icon: <ShoppingOutlined /> },
  { key: 'purchaser', email: 'purchaser@demo.my', password: 'Purchaser@123', icon: <ShoppingCartOutlined /> },
] as const

export default function LoginPage() {
  const { login } = useAuth()
  const { message } = App.useApp()
  const { t } = useTranslation('auth')
  const { token } = theme.useToken()
  const screens = useBreakpoint()
  const [loading, setLoading] = useState(false)
  const [prefill, setPrefill] = useState<{ email: string; password: string } | null>(null)

  const isWide = screens.lg

  const handleLogin = async (values: { email: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.email, values.password)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        t('loginFailed')
      message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const brandPanel = (
    <div
      style={{
        background: `linear-gradient(135deg, ${token.colorPrimary} 0%, #003eb3 100%)`,
        color: '#fff',
        padding: isWide ? '64px 56px' : '40px 32px',
        flex: isWide ? 1 : 'unset',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        gap: 24,
        minHeight: isWide ? '100vh' : 'auto',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <RocketOutlined style={{ fontSize: 36 }} />
        <Typography.Title level={2} style={{ color: '#fff', margin: 0 }}>
          {t('title')}
        </Typography.Title>
      </div>
      <Typography.Text style={{ color: 'rgba(255,255,255,0.9)', fontSize: 18 }}>
        {t('slogan')}
      </Typography.Text>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }}>
        <Tag icon={<ScanOutlined />} color="blue-inverse" style={{ padding: '4px 10px' }}>
          {t('highlights.ocr')}
        </Tag>
        <Tag icon={<AuditOutlined />} color="cyan-inverse" style={{ padding: '4px 10px' }}>
          {t('highlights.einvoice')}
        </Tag>
        <Tag icon={<GlobalOutlined />} color="geekblue-inverse" style={{ padding: '4px 10px' }}>
          {t('highlights.multiWarehouse')}
        </Tag>
      </div>
    </div>
  )

  const formPanel = (
    <div
      style={{
        flex: isWide ? 1 : 'unset',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: isWide ? '64px 32px' : '32px 16px',
        gap: 24,
        background: token.colorBgLayout,
      }}
    >
      <div style={{ width: '100%', maxWidth: 380 }}>
        <LoginForm
          title={t('title')}
          subTitle={t('subtitle')}
          loading={loading}
          onFinish={handleLogin}
          initialValues={prefill ?? {}}
          submitter={{ searchConfig: { submitText: t('form.submit') } }}
          key={JSON.stringify(prefill)}
        >
          <ProFormText
            name="email"
            fieldProps={{ prefix: <UserOutlined /> }}
            placeholder={t('form.email')}
            rules={[{ required: true, type: 'email', message: t('form.emailRequired') }]}
          />
          <ProFormText.Password
            name="password"
            fieldProps={{ prefix: <LockOutlined /> }}
            placeholder={t('form.password')}
            rules={[{ required: true, message: t('form.passwordRequired') }]}
          />
        </LoginForm>

        <Card
          title={<Typography.Text type="secondary">{t('demoAccounts')}</Typography.Text>}
          size="small"
          style={{ marginTop: 16 }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {DEMO_ACCOUNTS.map((acc) => {
              const active = prefill?.email === acc.email
              return (
                <div
                  key={acc.email}
                  onClick={() => setPrefill({ email: acc.email, password: acc.password })}
                  style={{
                    cursor: 'pointer',
                    padding: '10px 12px',
                    borderRadius: 6,
                    border: `1px solid ${active ? token.colorPrimary : token.colorBorderSecondary}`,
                    background: active ? token.colorPrimaryBg : token.colorBgContainer,
                    transition: 'all 0.15s',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: 18, color: token.colorPrimary, marginBottom: 4 }}>
                    {acc.icon}
                  </div>
                  <Typography.Text strong>{t(`roles.${acc.key}`)}</Typography.Text>
                  <br />
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                    {acc.email}
                  </Typography.Text>
                </div>
              )
            })}
          </div>
        </Card>
      </div>
    </div>
  )

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: isWide ? 'row' : 'column',
      }}
    >
      {brandPanel}
      {formPanel}
    </div>
  )
}
