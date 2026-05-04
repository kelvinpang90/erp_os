import { Statistic, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'

interface CountdownTimerProps {
  /** Seconds remaining when this component first mounts. */
  initialSeconds: number
  /** Total window length in seconds — used for the human-readable label. */
  windowSeconds: number
  /** Called once when the countdown reaches zero. */
  onElapsed?: () => void
}

const HOUR = 3600

function formatRemaining(secs: number): string {
  if (secs <= 0) return '0s'
  if (secs < HOUR) {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return m > 0 ? `${m}m ${s}s` : `${s}s`
  }
  const h = Math.floor(secs / HOUR)
  const m = Math.floor((secs - h * HOUR) / 60)
  return `${h}h ${m}m`
}

export default function CountdownTimer({
  initialSeconds,
  windowSeconds,
  onElapsed,
}: CountdownTimerProps) {
  const { t } = useTranslation('einvoice')
  const [remaining, setRemaining] = useState(initialSeconds)

  useEffect(() => {
    setRemaining(initialSeconds)
  }, [initialSeconds])

  useEffect(() => {
    if (remaining <= 0) {
      onElapsed?.()
      return
    }
    const id = setInterval(() => {
      setRemaining((s) => Math.max(s - 1, 0))
    }, 1000)
    return () => clearInterval(id)
  }, [remaining, onElapsed])

  const isDemo = windowSeconds <= 60 * 5  // ≤ 5 minutes → demo mode
  const label = isDemo
    ? t('opposition_window_demo', { seconds: windowSeconds })
    : t('opposition_window_prod', { hours: Math.round(windowSeconds / HOUR) })

  if (remaining <= 0) {
    return (
      <Typography.Text type="warning">
        <Trans i18nKey="einvoice:countdown.elapsedHint" components={{ b: <strong /> }} />
      </Typography.Text>
    )
  }

  return (
    <Statistic
      title={label}
      value={formatRemaining(remaining)}
      valueStyle={{ color: remaining < 30 ? '#cf1322' : '#1677ff', fontSize: 22 }}
    />
  )
}
