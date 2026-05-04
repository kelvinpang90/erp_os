import { App as AntApp, Space, Spin, Tag, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import AISummaryCard from './AISummaryCard'
import KPICards from './KPICards'
import TrendCharts from './TrendCharts'
import type { AISummaryEnvelope, DashboardOverviewResponse } from './types'

export default function DashboardPage() {
  const { t } = useTranslation('dashboard')
  const { message } = AntApp.useApp()
  const menu = useAuthStore((s) => s.menu)
  const [data, setData] = useState<DashboardOverviewResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  // Reports is only present in the role-filtered menu for Admin/Manager,
  // so its presence is a clean proxy for "can hit the refresh endpoint".
  const canRefresh = useMemo(
    () => menu.some((m) => m.path === '/reports'),
    [menu],
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axiosInstance.get<DashboardOverviewResponse>(
        '/dashboard/overview',
      )
      setData(res.data)
    } catch (err) {
      console.error('Dashboard overview failed', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleRefresh = async () => {
    if (!canRefresh) return
    setRefreshing(true)
    try {
      const res = await axiosInstance.post<AISummaryEnvelope>(
        '/dashboard/summary/refresh',
      )
      setData((prev) => (prev ? { ...prev, summary: res.data } : prev))
      if (res.data.error_code) {
        message.warning(t('summary.error_general'))
      } else {
        message.success(t('summary.fresh'))
      }
    } catch (err) {
      console.error('Refresh failed', err)
      message.error(t('summary.error_general'))
    } finally {
      setRefreshing(false)
    }
  }

  if (loading && !data) {
    return (
      <div style={{ padding: 80, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    )
  }
  if (!data) return null

  return (
    <Space direction="vertical" size="large" style={{ width: '100%', padding: 16 }}>
      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          {t('title')}
        </Typography.Title>
        <Tag color={data.cache_hit ? 'default' : 'green'}>
          {data.cache_hit ? t('cache.hit') : t('cache.fresh')}
        </Tag>
      </Space>

      <KPICards kpis={data.kpis} loading={loading} />

      <AISummaryCard
        envelope={data.summary}
        refreshing={refreshing}
        canRefresh={canRefresh}
        onRefresh={handleRefresh}
      />

      <TrendCharts trends={data.trends} />
    </Space>
  )
}
