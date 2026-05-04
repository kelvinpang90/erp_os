import {
  AlertOutlined,
  DollarOutlined,
  FileDoneOutlined,
  RobotOutlined,
  ShoppingCartOutlined,
  TruckOutlined,
} from '@ant-design/icons'
import { Card, Col, Row, Statistic } from 'antd'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { DashboardKPIs } from './types'

interface Props {
  kpis: DashboardKPIs
  loading?: boolean
}

interface KPIDef {
  key: keyof DashboardKPIs
  labelKey: string
  icon: ReactNode
  prefix?: string
  precision?: number
  color: string
}

const KPIS: KPIDef[] = [
  {
    key: 'today_sales',
    labelKey: 'kpi.today_sales',
    icon: <DollarOutlined />,
    prefix: 'RM',
    precision: 2,
    color: '#1677ff',
  },
  {
    key: 'today_purchases',
    labelKey: 'kpi.today_purchases',
    icon: <ShoppingCartOutlined />,
    prefix: 'RM',
    precision: 2,
    color: '#13c2c2',
  },
  {
    key: 'pending_shipments',
    labelKey: 'kpi.pending_shipments',
    icon: <TruckOutlined />,
    color: '#fa8c16',
  },
  {
    key: 'low_stock_count',
    labelKey: 'kpi.low_stock',
    icon: <AlertOutlined />,
    color: '#cf1322',
  },
  {
    key: 'pending_einvoices',
    labelKey: 'kpi.pending_einvoices',
    icon: <FileDoneOutlined />,
    color: '#722ed1',
  },
  {
    key: 'ai_cost_today_usd',
    labelKey: 'kpi.ai_cost_today',
    icon: <RobotOutlined />,
    prefix: '$',
    precision: 4,
    color: '#52c41a',
  },
]

export default function KPICards({ kpis, loading }: Props) {
  const { t } = useTranslation('dashboard')

  return (
    <Row gutter={[16, 16]}>
      {KPIS.map((def) => {
        const raw = kpis[def.key] as string | number
        const value =
          typeof raw === 'string' ? Number.parseFloat(raw) : (raw as number)

        return (
          <Col key={def.labelKey} xs={24} sm={12} md={8} xl={4}>
            <Card loading={loading} bordered hoverable>
              <Statistic
                title={
                  <span style={{ color: def.color, display: 'flex', gap: 6, alignItems: 'center' }}>
                    {def.icon}
                    {t(def.labelKey)}
                  </span>
                }
                value={Number.isFinite(value) ? value : 0}
                precision={def.precision ?? 0}
                prefix={def.prefix}
                valueStyle={{ color: def.color }}
              />
            </Card>
          </Col>
        )
      })}
    </Row>
  )
}
