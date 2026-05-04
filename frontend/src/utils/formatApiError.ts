import type { AxiosError } from 'axios'
import i18n from '../i18n'
import type { ApiErrorBody } from './errorCodes'

// Convert any axios/api error into a localized human-readable string.
// Order of preference: backend i18n_key (with args) > backend message > generic.
export function formatApiError(err: unknown, fallbackKey = 'errors:unknown'): string {
  const axErr = err as AxiosError<ApiErrorBody> | undefined
  const body = axErr?.response?.data

  if (body?.i18n_key) {
    // Backend keys are bare ("errors.insufficient_stock"); convert dot to colon for namespace lookup.
    const key = body.i18n_key.includes(':')
      ? body.i18n_key
      : body.i18n_key.replace(/^errors\./, 'errors:')
    const translated = i18n.t(key, body.i18n_args ?? {})
    if (translated && translated !== key) return String(translated)
  }

  if (body?.message) return body.message

  if (axErr && !axErr.response) {
    return i18n.t('errors:network_error') as string
  }

  return i18n.t(fallbackKey) as string
}
