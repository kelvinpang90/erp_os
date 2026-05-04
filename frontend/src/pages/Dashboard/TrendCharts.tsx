import { Card, Col, Empty, Row } from 'antd'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { DashboardTrends } from './types'

const COLORS = ['#1677ff', '#13c2c2', '#fa8c16', '#722ed1', '#cf1322', '#52c41a']

interface Props {
  trends: DashboardTrends
}

function pointsForLine(points: { bucket: string; value: string }[]) {
  return points.map((p) => ({ date: p.bucket.slice(5), value: Number.parseFloat(p.value) }))
}

export default function TrendCharts({ trends }: Props) {
  const { t } = useTranslation('dashboard')

  const sales = pointsForLine(trends.sales_last_30d)
  const purchase = pointsForLine(trends.purchase_last_30d)
  const aiCost = pointsForLine(trends.ai_cost_last_30d)
  const einvoiceData = trends.einvoice_status_distribution.map((b) => ({
    name: b.status,
    value: b.count,
  }))

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={12}>
        <Card title={t('trends.sales_30d')} size="small">
          <div style={{ height: 220 }}>
            {sales.length === 0 ? (
              <Empty />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sales}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#1677ff" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </Col>

      <Col xs={24} lg={12}>
        <Card title={t('trends.purchase_30d')} size="small">
          <div style={{ height: 220 }}>
            {purchase.length === 0 ? (
              <Empty />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={purchase}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#13c2c2" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </Col>

      <Col xs={24} lg={12}>
        <Card title={t('trends.einvoice_status')} size="small">
          <div style={{ height: 220 }}>
            {einvoiceData.length === 0 ? (
              <Empty />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={einvoiceData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    label
                  >
                    {einvoiceData.map((_, idx) => (
                      <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </Col>

      <Col xs={24} lg={12}>
        <Card title={t('trends.ai_cost_30d')} size="small">
          <div style={{ height: 220 }}>
            {aiCost.length === 0 ? (
              <Empty />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={aiCost}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#52c41a" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </Col>
    </Row>
  )
}
