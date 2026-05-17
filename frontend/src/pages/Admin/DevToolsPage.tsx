import { CaretRightOutlined, PauseOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  List,
  Row,
  Space,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { axiosInstance } from '../../api/client'

interface LiveEvent {
  event_type: string
  occurred_at: string
  payload: Record<string, unknown>
  receivedAt: string
}

interface HistoryRow {
  id: number
  event_type: string
  organization_id: number | null
  actor_user_id: number | null
  request_id: string | null
  payload: Record<string, unknown> | null
  occurred_at: string
}

const EVENT_COLORS: Record<string, string> = {
  DocumentStatusChanged: 'blue',
  StockMovementOccurred: 'orange',
  EInvoiceValidated: 'green',
}

const MAX_LIVE_BUFFER = 100

export default function DevToolsPage() {
  const { t } = useTranslation('admin')
  const [live, setLive] = useState<LiveEvent[]>([])
  const [history, setHistory] = useState<HistoryRow[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [paused, setPaused] = useState(false)
  const [connected, setConnected] = useState(false)
  const esRef = useRef<EventSource | null>(null)
  const pausedRef = useRef(paused)

  useEffect(() => {
    pausedRef.current = paused
  }, [paused])

  useEffect(() => {
    void loadHistory()
    openStream()
    return () => closeStream()
  }, [])

  function openStream() {
    closeStream()
    const token = localStorage.getItem('access_token') ?? ''
    // EventSource cannot set headers; ship token via query string. The
    // backend dependency reads it from Authorization header normally,
    // so we accept that admins re-auth via cookie or extension if missing.
    // For demo simplicity we use the existing access_token via a custom
    // querystring our backend ignores; the dependency will fail with 401
    // if the token isn't present in the header. Most browsers send
    // cookies along, so this works behind nginx with the same origin.
    const url = `/api/admin/events/stream${token ? `?token=${encodeURIComponent(token)}` : ''}`
    const es = new EventSource(url, { withCredentials: true })
    esRef.current = es

    es.addEventListener('hello', () => setConnected(true))
    es.addEventListener('ping', () => {
      // keep-alive — no-op
    })
    es.addEventListener('domain_event', (raw: MessageEvent) => {
      if (pausedRef.current) return
      try {
        const data = JSON.parse(raw.data) as Omit<LiveEvent, 'receivedAt'>
        setLive((prev) => {
          const next = [{ ...data, receivedAt: new Date().toISOString() }, ...prev]
          return next.slice(0, MAX_LIVE_BUFFER)
        })
      } catch {
        // ignore malformed
      }
    })
    es.onerror = () => setConnected(false)
  }

  function closeStream() {
    esRef.current?.close()
    esRef.current = null
  }

  async function loadHistory() {
    setHistoryLoading(true)
    try {
      const res = await axiosInstance.get<{ items: HistoryRow[] }>('/admin/events', {
        params: { page: 1, page_size: 50 },
      })
      setHistory(res.data.items)
    } finally {
      setHistoryLoading(false)
    }
  }

  function clearLive() {
    setLive([])
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        {t('dev_tools.title')}
      </Typography.Title>
      <Typography.Paragraph type="secondary">{t('dev_tools.subtitle')}</Typography.Paragraph>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card
            title={
              <Space>
                {t('dev_tools.live')}
                <Badge
                  status={connected ? (paused ? 'warning' : 'success') : 'error'}
                  text={
                    connected
                      ? paused
                        ? t('dev_tools.status_paused')
                        : t('dev_tools.status_live')
                      : t('dev_tools.status_disconnected')
                  }
                />
              </Space>
            }
            extra={
              <Space>
                <Tooltip title={paused ? t('dev_tools.resume') : t('dev_tools.pause')}>
                  <Button
                    icon={paused ? <CaretRightOutlined /> : <PauseOutlined />}
                    onClick={() => setPaused((v) => !v)}
                  />
                </Tooltip>
                <Button onClick={clearLive}>{t('dev_tools.clear')}</Button>
              </Space>
            }
          >
            {live.length === 0 ? (
              <Empty description={t('dev_tools.empty_live')} />
            ) : (
              <List
                size="small"
                dataSource={live}
                renderItem={(e) => <EventRow key={e.receivedAt} type={e.event_type} time={e.receivedAt} payload={e.payload} />}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card
            title={t('dev_tools.history')}
            extra={
              <Tooltip title={t('dev_tools.refresh')}>
                <Button icon={<ReloadOutlined />} loading={historyLoading} onClick={() => void loadHistory()} />
              </Tooltip>
            }
          >
            {history.length === 0 ? (
              <Empty description={t('dev_tools.empty_history')} />
            ) : (
              <List
                size="small"
                dataSource={history}
                renderItem={(e) => (
                  <EventRow
                    key={e.id}
                    type={e.event_type}
                    time={e.occurred_at}
                    payload={e.payload ?? {}}
                  />
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </Space>
  )
}

function EventRow({
  type,
  time,
  payload,
}: {
  type: string
  time: string
  payload: Record<string, unknown>
}) {
  const color = EVENT_COLORS[type] ?? 'default'
  const summary = pickSummary(type, payload)
  return (
    <List.Item style={{ display: 'block' }}>
      <Space size={8} wrap style={{ marginBottom: 4 }}>
        <Tag color={color}>{type}</Tag>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {dayjs(time).format('HH:mm:ss')}
        </Typography.Text>
      </Space>
      <pre
        style={{
          background: 'rgba(0,0,0,0.04)',
          padding: 8,
          margin: 0,
          fontSize: 12,
          overflow: 'auto',
          maxHeight: 160,
        }}
      >
        {summary}
      </pre>
    </List.Item>
  )
}

function pickSummary(type: string, payload: Record<string, unknown>): string {
  // Show the most informative subset for the three core event types,
  // fall back to the full JSON dump for anything else.
  if (type === 'DocumentStatusChanged') {
    const p = payload as Record<string, unknown>
    return JSON.stringify(
      {
        document_type: p.document_type,
        document_no: p.document_no,
        old: p.old_status,
        new: p.new_status,
        actor: p.actor_user_id,
      },
      null,
      2,
    )
  }
  if (type === 'StockMovementOccurred') {
    const p = payload as Record<string, unknown>
    return JSON.stringify(
      {
        sku_id: p.sku_id,
        warehouse_id: p.warehouse_id,
        movement_type: p.movement_type,
        qty: p.quantity,
        source: `${p.source_document_type}#${p.source_document_id}`,
      },
      null,
      2,
    )
  }
  if (type === 'EInvoiceValidated') {
    const p = payload as Record<string, unknown>
    return JSON.stringify(
      { invoice_no: p.invoice_no, uin: p.uin, validated_at: p.validated_at },
      null,
      2,
    )
  }
  return JSON.stringify(payload, null, 2)
}
