import {
  ApartmentOutlined,
  BankOutlined,
  DollarOutlined,
  HomeOutlined,
  PercentageOutlined,
  RobotOutlined,
  SettingOutlined,
  TagsOutlined,
  TeamOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'
import { Card, Col, Row, Typography } from 'antd'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

interface SettingCard {
  key: string
  icon: ReactNode
  path?: string
  disabled?: boolean
}

const CARDS: SettingCard[] = [
  { key: 'general', icon: <SettingOutlined />, disabled: true },
  { key: 'currencies', icon: <DollarOutlined />, path: '/settings/currencies' },
  { key: 'tax_rates', icon: <PercentageOutlined />, path: '/settings/tax-rates' },
  { key: 'uoms', icon: <UnorderedListOutlined />, path: '/settings/uoms' },
  { key: 'brands', icon: <TagsOutlined />, path: '/settings/brands' },
  { key: 'categories', icon: <ApartmentOutlined />, path: '/settings/categories' },
  { key: 'warehouses', icon: <HomeOutlined />, path: '/settings/warehouses' },
  { key: 'ai_features', icon: <RobotOutlined />, path: '/settings/ai-features' },
  { key: 'users', icon: <TeamOutlined />, path: '/settings/users' },
]

export default function SettingsHubPage() {
  const { t } = useTranslation('settings')
  const navigate = useNavigate()

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        <BankOutlined style={{ marginRight: 8 }} />
        {t('title')}
      </Typography.Title>
      <Typography.Paragraph type="secondary">{t('description')}</Typography.Paragraph>
      <Row gutter={[16, 16]}>
        {CARDS.map((card) => (
          <Col key={card.key} xs={24} sm={12} md={8} lg={8} xl={6}>
            <Card
              hoverable={!card.disabled}
              onClick={() => {
                if (card.disabled || !card.path) return
                navigate(card.path)
              }}
              style={{
                cursor: card.disabled ? 'not-allowed' : 'pointer',
                opacity: card.disabled ? 0.6 : 1,
                height: '100%',
              }}
            >
              <Card.Meta
                avatar={<span style={{ fontSize: 28 }}>{card.icon}</span>}
                title={t(`cards.${card.key}.title`)}
                description={t(`cards.${card.key}.desc`)}
              />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
}
