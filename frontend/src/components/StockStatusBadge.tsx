import { Space, Tag, Tooltip } from 'antd'

export interface StockSnapshot {
  on_hand?: number | string
  reserved?: number | string
  quality_hold?: number | string
  available?: number | string
  incoming?: number | string
  in_transit?: number | string
}

interface Props {
  stock: StockSnapshot
  compact?: boolean
}

/**
 * 6-dimension stock badge.
 *
 * Compact mode (compact=true): only on_hand + available, suitable for table rows.
 * Full mode (default): all 6 dimensions, suitable for detail panels and tooltips.
 */
export default function StockStatusBadge({ stock, compact = false }: Props) {
  const fmt = (val: number | string | undefined) => {
    if (val === undefined || val === null) return '0'
    const n = typeof val === 'string' ? parseFloat(val) : val
    return n.toLocaleString('en-MY', { maximumFractionDigits: 2 })
  }

  const fullView = (
    <Space direction="vertical" size={4}>
      <Tag color="blue">On Hand: {fmt(stock.on_hand)}</Tag>
      <Tag color="orange">Reserved: {fmt(stock.reserved)}</Tag>
      <Tag color="purple">QualityHold: {fmt(stock.quality_hold)}</Tag>
      <Tag color="green">Available: {fmt(stock.available)}</Tag>
      <Tag color="cyan">Incoming: {fmt(stock.incoming)}</Tag>
      <Tag color="gold">InTransit: {fmt(stock.in_transit)}</Tag>
    </Space>
  )

  if (!compact) {
    return fullView
  }

  return (
    <Tooltip title={fullView} placement="top">
      <Space size={4}>
        <Tag color="blue">{fmt(stock.on_hand)}</Tag>
        <Tag color="green">/{fmt(stock.available)}</Tag>
      </Space>
    </Tooltip>
  )
}
