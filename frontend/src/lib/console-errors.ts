import { isTransportError, type TransportError } from '@/lib/api'

function safeDetail(error: TransportError): string | undefined {
  return typeof error.details === 'string' && error.details.length <= 240
    ? error.details
    : undefined
}

/** Convert a normalized transport failure into an actionable operator-facing message. */
export function getConsoleErrorMessage(error: unknown): string {
  if (!isTransportError(error)) {
    return error instanceof Error && error.message
      ? error.message
      : 'The request could not be completed.'
  }

  const detail = safeDetail(error)
  switch (error.kind) {
    case 'UNAUTHENTICATED':
      return 'Your session has expired. Sign in again to continue.'
    case 'FORBIDDEN':
      return 'Your current access does not include this operation.'
    case 'CONFLICT':
      return detail
        ? `The server state changed: ${detail}`
        : 'The server state changed. Refresh the page before trying again.'
    case 'VALIDATION':
      return detail
        ? `Check the submitted values: ${detail}`
        : 'Check the submitted values and try again.'
    case 'RATE_LIMITED':
      return 'The service is rate limiting this operation. Wait a moment and retry manually.'
    case 'TIMEOUT':
      return 'The service did not respond in time. Retry manually when ready.'
    case 'NETWORK':
      return 'The network connection failed. Check connectivity and retry manually.'
    case 'SERVER':
      return 'The service is temporarily unavailable. Retry manually when ready.'
    case 'ABORTED':
      return 'The request was cancelled.'
    default:
      return detail ?? 'The request could not be completed.'
  }
}

export function isForbiddenError(error: unknown): boolean {
  return isTransportError(error) && error.kind === 'FORBIDDEN'
}
