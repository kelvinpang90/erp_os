// Mirror of backend/app/core/exceptions.py error codes.
// Keep in sync manually; if/when orval supports exception schema export, switch to generated.
export const ErrorCodes = {
  AUTHENTICATION_REQUIRED: 'AUTHENTICATION_REQUIRED',
  INVALID_CREDENTIALS: 'INVALID_CREDENTIALS',
  TOKEN_EXPIRED: 'TOKEN_EXPIRED',
  TOKEN_INVALID: 'TOKEN_INVALID',
  ACCOUNT_LOCKED: 'ACCOUNT_LOCKED',
  TOO_MANY_ATTEMPTS: 'TOO_MANY_ATTEMPTS',
  PERMISSION_DENIED: 'PERMISSION_DENIED',
  NOT_FOUND: 'NOT_FOUND',
  CONFLICT: 'CONFLICT',
  BUSINESS_RULE_VIOLATION: 'BUSINESS_RULE_VIOLATION',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  INSUFFICIENT_STOCK: 'INSUFFICIENT_STOCK',
  INVALID_STATUS_TRANSITION: 'INVALID_STATUS_TRANSITION',
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',
  AI_FEATURE_DISABLED: 'AI_FEATURE_DISABLED',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
} as const

export type ErrorCode = keyof typeof ErrorCodes

export interface ApiErrorBody {
  error_code: string
  message: string
  i18n_key?: string
  i18n_args?: Record<string, unknown>
  detail?: unknown
  request_id?: string
  timestamp?: string
}
