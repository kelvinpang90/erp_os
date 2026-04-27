import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { LoginForm, ProFormText } from '@ant-design/pro-components'
import { App, Card, Typography } from 'antd'
import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'

const DEMO_ACCOUNTS = [
  { label: 'Admin', email: 'admin@demo.my', password: 'Admin@123' },
  { label: 'Manager', email: 'manager@demo.my', password: 'Manager@123' },
  { label: 'Sales', email: 'sales@demo.my', password: 'Sales@123' },
  { label: 'Purchaser', email: 'purchaser@demo.my', password: 'Purchaser@123' },
]

export default function LoginPage() {
  const { login } = useAuth()
  const { message } = App.useApp()
  const [loading, setLoading] = useState(false)
  const [prefill, setPrefill] = useState<{ email: string; password: string } | null>(null)

  const handleLogin = async (values: { email: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.email, values.password)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        'Login failed. Please check your credentials.'
      message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f0f2f5',
        gap: 24,
      }}
    >
      <LoginForm
        title="ERP OS"
        subTitle="Malaysia SME ERP System"
        loading={loading}
        onFinish={handleLogin}
        initialValues={prefill ?? {}}
        key={JSON.stringify(prefill)}
      >
        <ProFormText
          name="email"
          fieldProps={{ prefix: <UserOutlined /> }}
          placeholder="Email"
          rules={[{ required: true, type: 'email' }]}
        />
        <ProFormText.Password
          name="password"
          fieldProps={{ prefix: <LockOutlined /> }}
          placeholder="Password"
          rules={[{ required: true }]}
        />
      </LoginForm>

      <Card
        title={<Typography.Text type="secondary">Demo Accounts (click to fill)</Typography.Text>}
        size="small"
        style={{ width: 380 }}
      >
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {DEMO_ACCOUNTS.map((acc) => (
            <Card.Grid
              key={acc.email}
              style={{ width: '50%', padding: '8px 12px', cursor: 'pointer', textAlign: 'center' }}
              onClick={() => setPrefill({ email: acc.email, password: acc.password })}
            >
              <Typography.Text strong>{acc.label}</Typography.Text>
              <br />
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                {acc.email}
              </Typography.Text>
            </Card.Grid>
          ))}
        </div>
      </Card>
    </div>
  )
}
