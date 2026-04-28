/**
 * Generic SSE-aware uploader.
 *
 * Why not Ant Design <Upload> with `customRequest`? <Upload>'s contract is
 * one HTTP exchange ending in success/error — it can't surface per-stage
 * progress events from an SSE stream. So we use a thin Dragger UI for the
 * drop zone but drive the actual POST with `fetch` + `ReadableStream` so we
 * can parse `event: ...\ndata: ...\n\n` frames as they arrive.
 *
 * Server contract (matches /api/ai/ocr/purchase-order):
 *   event: progress  data: {"stage": "...", "progress": 0-100, ...}
 *   event: done      data: {"stage": "done", "progress": 100, "result": {...}}
 *   event: error     data: {"code": "...", "message": "..."}
 */

import { InboxOutlined } from '@ant-design/icons'
import { App, Alert, Progress, Typography, Upload } from 'antd'
import type { UploadFile, RcFile } from 'antd/es/upload/interface'
import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'

const { Dragger } = Upload

export interface SSEProgressEvent {
  stage: 'uploaded' | 'calling_ai' | 'parsing' | 'done' | 'error'
  progress: number
  // Additional payload fields (e.g. file_id) live alongside but are not used here.
  [key: string]: unknown
}

export interface SSEDoneEvent<TResult> {
  stage: 'done'
  progress: 100
  result: TResult
}

export interface SSEErrorEvent {
  code: string
  message: string
}

export interface SSEUploaderProps<TResult> {
  endpoint: string
  accept: string
  maxSizeMB: number
  /** i18n namespace prefix for translated stage / error labels. */
  i18nNs?: string
  onSuccess: (result: TResult) => void
  onError?: (err: SSEErrorEvent) => void
  /** Optional override for the disabled-button label / drag hint. */
  uploadHint?: string
  acceptHint?: string
}

interface SSEFrame {
  event: string
  data: string
}

/**
 * Parse a chunk of SSE text into discrete frames. Maintains a buffer for
 * partial frames split across reads.
 */
function makeSSEParser(): (chunk: string) => SSEFrame[] {
  let buffer = ''
  return (chunk: string) => {
    buffer += chunk
    const frames: SSEFrame[] = []
    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)

      let event = 'message'
      const dataLines: string[] = []
      for (const line of raw.split('\n')) {
        if (line.startsWith(':')) continue // comment / keepalive
        if (line.startsWith('event:')) {
          event = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trimStart())
        }
      }
      if (dataLines.length > 0) {
        frames.push({ event, data: dataLines.join('\n') })
      }
    }
    return frames
  }
}

export default function SSEUploader<TResult>({
  endpoint,
  accept,
  maxSizeMB,
  i18nNs = 'ocr',
  onSuccess,
  onError,
  uploadHint,
  acceptHint,
}: SSEUploaderProps<TResult>) {
  const { t } = useTranslation(i18nNs)
  const { message } = App.useApp()

  const [uploading, setUploading] = useState(false)
  const [stage, setStage] = useState<SSEProgressEvent['stage'] | null>(null)
  const [progress, setProgress] = useState(0)
  const [errorBox, setErrorBox] = useState<SSEErrorEvent | null>(null)

  const reset = useCallback(() => {
    setUploading(false)
    setStage(null)
    setProgress(0)
    setErrorBox(null)
  }, [])

  const upload = useCallback(
    async (file: RcFile) => {
      if (file.size > maxSizeMB * 1024 * 1024) {
        message.error(t('errors.file_too_large', { size: maxSizeMB }))
        return false
      }

      reset()
      setUploading(true)

      const formData = new FormData()
      formData.append('file', file)
      const token = localStorage.getItem('access_token')

      let response: Response
      try {
        response = await fetch(endpoint, {
          method: 'POST',
          body: formData,
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        })
      } catch (e) {
        const err: SSEErrorEvent = {
          code: 'NETWORK_ERROR',
          message: t('errors.network'),
        }
        setErrorBox(err)
        setUploading(false)
        onError?.(err)
        return false
      }

      if (!response.ok) {
        // Non-streaming error (e.g. 401, 422 AI_FEATURE_DISABLED, 429 quota)
        let body: { error_code?: string; message?: string } = {}
        try {
          body = await response.json()
        } catch {
          /* ignore */
        }
        const err: SSEErrorEvent = {
          code: body.error_code ?? `HTTP_${response.status}`,
          message: body.message ?? t('errors.generic'),
        }
        setErrorBox(err)
        setUploading(false)
        onError?.(err)
        return false
      }

      const reader = response.body?.getReader()
      if (!reader) {
        const err: SSEErrorEvent = {
          code: 'NO_STREAM',
          message: t('errors.no_stream'),
        }
        setErrorBox(err)
        setUploading(false)
        onError?.(err)
        return false
      }

      const decoder = new TextDecoder()
      const parse = makeSSEParser()
      let succeeded = false

      try {
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const chunk = decoder.decode(value, { stream: true })
          for (const frame of parse(chunk)) {
            if (frame.event === 'progress') {
              const ev = JSON.parse(frame.data) as SSEProgressEvent
              setStage(ev.stage)
              setProgress(ev.progress)
            } else if (frame.event === 'done') {
              const ev = JSON.parse(frame.data) as SSEDoneEvent<TResult>
              setStage('done')
              setProgress(100)
              succeeded = true
              onSuccess(ev.result)
            } else if (frame.event === 'error') {
              const ev = JSON.parse(frame.data) as SSEErrorEvent
              setErrorBox(ev)
              onError?.(ev)
            }
          }
        }
      } catch (e) {
        const err: SSEErrorEvent = {
          code: 'STREAM_ABORTED',
          message: t('errors.stream_aborted'),
        }
        setErrorBox(err)
        onError?.(err)
      } finally {
        setUploading(false)
      }

      return succeeded
    },
    [endpoint, maxSizeMB, message, onError, onSuccess, reset, t],
  )

  return (
    <div>
      <Dragger
        accept={accept}
        multiple={false}
        showUploadList={false}
        disabled={uploading}
        beforeUpload={(file) => {
          // Drive the upload manually; return false so antd doesn't try its own POST.
          void upload(file)
          return false
        }}
        onChange={(info: { file: UploadFile }) => {
          // Antd fires onChange even with beforeUpload=false; ignore it.
          void info
        }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">{uploadHint ?? t('drag_hint')}</p>
        <p className="ant-upload-hint">{acceptHint ?? t('accept_hint', { size: maxSizeMB })}</p>
      </Dragger>

      {(uploading || stage) && stage !== 'error' && (
        <div style={{ marginTop: 16 }}>
          <Progress
            percent={progress}
            status={stage === 'done' ? 'success' : 'active'}
            showInfo
          />
          <Typography.Text type="secondary">
            {stage ? t(`stages.${stage}`) : t('stages.uploaded')}
          </Typography.Text>
        </div>
      )}

      {errorBox && (
        <Alert
          style={{ marginTop: 16 }}
          type="warning"
          showIcon
          message={t('errors.title')}
          description={errorBox.message || t(`errors.${errorBox.code}`, errorBox.message)}
        />
      )}
    </div>
  )
}
