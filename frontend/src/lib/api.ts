import { useAuthStore } from '@/stores/auth'

export const SESSION_INVALIDATED_EVENT = 'star-warehouse:session-invalidated'
export const ACCESS_DENIED_EVENT = 'star-warehouse:access-denied'

export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
export const CSRF_HEADER_NAME = 'X-CSRF-Token'

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE'])
const DEFAULT_REQUEST_TIMEOUT_MS = 15_000
const CSRF_REQUEST_TIMEOUT_MS = 10_000
const MAX_RETRY_ATTEMPTS = 3
const MAX_RETRY_DELAY_MS = 5_000
const MAX_RETRY_AFTER_MS = 5_000
const MAX_ERROR_DETAIL_LENGTH = 500
const SAFE_IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$/
const AUTHENTICATION_QUERY_KEYS = new Set(['token', 'access_token', 'jwt', 'authorization'])
const SENSITIVE_ERROR_KEYS = new Set([
  'access_token',
  'authorization',
  'cookie',
  'csrf',
  'csrf_token',
  'password',
  'refresh_token',
  'secret',
  'session_token',
  'token',
])

let csrfToken: string | null = null
let csrfRequest: Promise<string> | null = null
let csrfGeneration = 0

export type TransportErrorKind =
  | 'NETWORK'
  | 'TIMEOUT'
  | 'ABORTED'
  | 'UNAUTHENTICATED'
  | 'FORBIDDEN'
  | 'CONFLICT'
  | 'VALIDATION'
  | 'RATE_LIMITED'
  | 'SERVER'
  | 'UNKNOWN'

export type SafeErrorDetail =
  | string
  | number
  | boolean
  | null
  | SafeErrorDetail[]
  | { [key: string]: SafeErrorDetail }

export interface RetryPolicy {
  /** Total attempts, including the initial request. */
  maxAttempts?: number
  baseDelayMs?: number
  maxDelayMs?: number
  jitterRatio?: number
}

export interface TransportErrorOptions {
  kind: TransportErrorKind
  message?: string
  status?: number
  code?: string
  details?: SafeErrorDetail
  requestId?: string
  correlationId?: string
  retryAfterMs?: number
  route?: string
  cause?: unknown
}

export class TransportError extends Error {
  readonly kind: TransportErrorKind
  readonly status?: number
  readonly code?: string
  readonly details?: SafeErrorDetail
  readonly requestId?: string
  readonly correlationId?: string
  readonly retryAfterMs?: number
  readonly route?: string
  readonly cause?: unknown

  constructor(options: TransportErrorOptions) {
    super(options.message || defaultTransportMessage(options.kind))
    this.name = 'TransportError'
    this.kind = options.kind
    this.status = options.status
    this.code = options.code
    this.details = options.details
    this.requestId = options.requestId
    this.correlationId = options.correlationId
    this.retryAfterMs = options.retryAfterMs
    this.route = options.route
    this.cause = options.cause
  }
}

export interface ApiFetchOptions extends RequestInit {
  /** Kept for compatibility; 401 never causes an automatic navigation. */
  skip401Redirect?: boolean
  /** Login is the only current browser request that intentionally skips CSRF. */
  skipCsrf?: boolean
  /** Set to 0 to disable the request deadline for a long-lived transport. */
  timeoutMs?: number
  /** Safe reads get a bounded default; mutation retries require an idempotency key. */
  retry?: RetryPolicy | false
  /** Forward only a domain-owned, bounded logical-operation key. */
  idempotencyKey?: string
  /** Forward only a safe caller-owned correlation identifier. */
  correlationId?: string
}

interface AttemptSignal {
  signal: AbortSignal
  timedOut: () => boolean
  callerAborted: () => boolean
  cleanup: () => void
}

function defaultTransportMessage(kind: TransportErrorKind): string {
  switch (kind) {
    case 'NETWORK':
      return 'The network connection failed.'
    case 'TIMEOUT':
      return 'The request timed out.'
    case 'ABORTED':
      return 'The request was cancelled.'
    case 'UNAUTHENTICATED':
      return 'Your session is no longer authenticated.'
    case 'FORBIDDEN':
      return 'You are not allowed to perform this action.'
    case 'CONFLICT':
      return 'The request conflicts with current server state.'
    case 'VALIDATION':
      return 'The request contains invalid data.'
    case 'RATE_LIMITED':
      return 'Too many requests. Please try again later.'
    case 'SERVER':
      return 'The service is temporarily unavailable.'
    default:
      return 'The request could not be completed.'
  }
}

export function isTransportError(error: unknown): error is TransportError {
  return error instanceof TransportError
}

function isAbortError(error: unknown): boolean {
  return (
    (typeof DOMException !== 'undefined' &&
      error instanceof DOMException &&
      error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'AbortError')
  )
}

export function normalizeTransportError(
  error: unknown,
  options: { route?: string; signal?: AbortSignal; timedOut?: boolean } = {}
): TransportError {
  if (isTransportError(error)) return error

  if (options.timedOut) {
    return new TransportError({
      kind: 'TIMEOUT',
      route: options.route,
      cause: error,
    })
  }

  if (options.signal?.aborted || isAbortError(error)) {
    return new TransportError({
      kind: 'ABORTED',
      route: options.route,
      cause: error,
    })
  }

  return new TransportError({
    kind: 'NETWORK',
    route: options.route,
    cause: error,
  })
}

function createAbortedError(route?: string): TransportError {
  return new TransportError({ kind: 'ABORTED', route })
}

function createAttemptSignal(callerSignal: AbortSignal | null, timeoutMs: number): AttemptSignal {
  const controller = new AbortController()
  let didTimeout = false
  let didCallerAbort = Boolean(callerSignal?.aborted)
  let timeoutId: ReturnType<typeof setTimeout> | undefined

  const abortFromCaller = (): void => {
    didCallerAbort = true
    controller.abort()
  }

  if (callerSignal) {
    if (callerSignal.aborted) controller.abort()
    else callerSignal.addEventListener('abort', abortFromCaller, { once: true })
  }

  if (timeoutMs > 0) {
    timeoutId = setTimeout(() => {
      didTimeout = true
      controller.abort()
    }, timeoutMs)
  }

  return {
    signal: controller.signal,
    timedOut: () => didTimeout,
    callerAborted: () => didCallerAbort,
    cleanup: () => {
      if (timeoutId !== undefined) clearTimeout(timeoutId)
      callerSignal?.removeEventListener('abort', abortFromCaller)
    },
  }
}

function buildApiUrl(input: string): string {
  const url = /^https?:\/\//i.test(input)
    ? new URL(input).toString()
    : `${API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE}${input.startsWith('/') ? input : `/${input}`}`
  const parsed = new URL(
    url,
    typeof window !== 'undefined' ? window.location.href : 'http://localhost/'
  )
  if (
    [...parsed.searchParams.keys()].some((key) => AUTHENTICATION_QUERY_KEYS.has(key.toLowerCase()))
  ) {
    throw new TypeError('Browser transport URLs must not contain authentication query parameters')
  }
  const fragment = new URLSearchParams(parsed.hash.slice(1))
  if ([...fragment.keys()].some((key) => AUTHENTICATION_QUERY_KEYS.has(key.toLowerCase()))) {
    throw new TypeError('Browser transport URLs must not contain authentication fragments')
  }
  return url
}

function isFormDataBody(body: BodyInit | null | undefined): boolean {
  return typeof FormData !== 'undefined' && body instanceof FormData
}

function buildHeaders(
  inputHeaders: HeadersInit | undefined,
  body: BodyInit | null | undefined,
  csrf: string | null,
  idempotencyKey: string | undefined,
  correlationId: string | undefined
): Headers {
  const headers = new Headers(inputHeaders)
  if (headers.has('Authorization')) {
    throw new TypeError('Browser transport does not accept Authorization headers')
  }
  if (
    body !== undefined &&
    body !== null &&
    !isFormDataBody(body) &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json')
  }
  if (csrf !== null) headers.set(CSRF_HEADER_NAME, csrf)
  if (idempotencyKey !== undefined) headers.set('Idempotency-Key', idempotencyKey)
  if (correlationId !== undefined) headers.set('X-Correlation-ID', correlationId)
  return headers
}

function isSafeIdentifier(value: string): boolean {
  return SAFE_IDENTIFIER_PATTERN.test(value)
}

function validateOptionalIdentifier(value: string | undefined, name: string): string | undefined {
  if (value === undefined) return undefined
  if (!isSafeIdentifier(value)) throw new TypeError(`${name} must be a bounded safe identifier`)
  return value
}

function normalizeRetryPolicy(
  method: string,
  retry: RetryPolicy | false | undefined,
  idempotencyKey: string | undefined
): RetryPolicy | null {
  if (retry === false) return null
  if (retry === undefined) {
    return SAFE_METHODS.has(method) ? { maxAttempts: 2, baseDelayMs: 150, maxDelayMs: 1_000 } : null
  }
  if (!SAFE_METHODS.has(method) && idempotencyKey === undefined) return null

  const maxAttempts = Math.min(MAX_RETRY_ATTEMPTS, Math.max(1, Math.floor(retry.maxAttempts ?? 2)))
  const baseDelayMs = Math.max(0, Math.min(MAX_RETRY_DELAY_MS, retry.baseDelayMs ?? 150))
  const maxDelayMs = Math.max(baseDelayMs, Math.min(MAX_RETRY_DELAY_MS, retry.maxDelayMs ?? 1_000))
  const jitterRatio = Math.max(0, Math.min(0.5, retry.jitterRatio ?? 0.2))
  return { maxAttempts, baseDelayMs, maxDelayMs, jitterRatio }
}

function isRetryableStatus(status: number): boolean {
  return status === 408 || status === 425 || status === 429 || status >= 500
}

function isRetryableTransportError(error: TransportError): boolean {
  return error.kind === 'NETWORK' || error.kind === 'TIMEOUT'
}

function retryDelayMs(policy: RetryPolicy, failedAttempt: number, retryAfterMs?: number): number {
  const maxDelayMs = policy.maxDelayMs ?? 1_000
  if (retryAfterMs !== undefined) return Math.min(maxDelayMs, retryAfterMs)
  const baseDelayMs = policy.baseDelayMs ?? 150
  const delay = Math.min(maxDelayMs, baseDelayMs * 2 ** Math.max(0, failedAttempt - 1))
  const jitterRatio = policy.jitterRatio ?? 0.2
  const jitter = delay * jitterRatio * (Math.random() * 2 - 1)
  return Math.max(0, Math.round(delay + jitter))
}

function waitWithAbort(delayMs: number, signal: AbortSignal | null, route: string): Promise<void> {
  if (signal?.aborted) return Promise.reject(createAbortedError(route))
  if (delayMs <= 0) return Promise.resolve()

  return new Promise<void>((resolve, reject) => {
    const abort = (): void => {
      clearTimeout(timerId)
      signal?.removeEventListener('abort', abort)
      reject(createAbortedError(route))
    }
    const timerId = setTimeout(() => {
      signal?.removeEventListener('abort', abort)
      resolve()
    }, delayMs)
    signal?.addEventListener('abort', abort, { once: true })
  })
}

function retryAfterMs(response: Response): number | undefined {
  const raw = response.headers.get('Retry-After')
  if (!raw) return undefined
  const seconds = Number(raw)
  const duration = Number.isFinite(seconds)
    ? Math.max(0, seconds * 1_000)
    : Date.parse(raw) - Date.now()
  if (!Number.isFinite(duration)) return undefined
  return Math.min(MAX_RETRY_AFTER_MS, duration)
}

function headerValue(response: Response, ...names: string[]): string | undefined {
  for (const name of names) {
    const value = response.headers.get(name)
    if (value && isSafeIdentifier(value)) return value
  }
  return undefined
}

function sanitizeString(value: string): string {
  const bounded = value.trim().slice(0, MAX_ERROR_DETAIL_LENGTH)
  if (/\b(?:bearer\s+)?ey[a-z0-9_-]{20,}\.?/i.test(bounded)) return '[redacted]'
  return bounded
}

function sanitizeErrorValue(value: unknown, depth = 0, key = ''): SafeErrorDetail | undefined {
  if (SENSITIVE_ERROR_KEYS.has(key.toLowerCase())) return undefined
  if (typeof value === 'string') return sanitizeString(value)
  if (typeof value === 'number' || typeof value === 'boolean' || value === null) return value
  if (depth >= 3 || typeof value !== 'object') return undefined

  if (Array.isArray(value)) {
    return value
      .slice(0, 20)
      .map((item) => sanitizeErrorValue(item, depth + 1))
      .filter((item): item is SafeErrorDetail => item !== undefined)
  }

  const safeObject: { [key: string]: SafeErrorDetail } = {}
  for (const [childKey, childValue] of Object.entries(value as Record<string, unknown>).slice(
    0,
    20
  )) {
    const sanitized = sanitizeErrorValue(childValue, depth + 1, childKey)
    if (sanitized !== undefined) safeObject[childKey] = sanitized
  }
  return safeObject
}

function errorKindForStatus(status: number): TransportErrorKind {
  if (status === 401) return 'UNAUTHENTICATED'
  if (status === 403) return 'FORBIDDEN'
  if (status === 409) return 'CONFLICT'
  if (status === 422) return 'VALIDATION'
  if (status === 429) return 'RATE_LIMITED'
  if (status >= 500) return 'SERVER'
  return 'UNKNOWN'
}

function detailFromPayload(payload: unknown): { code?: string; details?: SafeErrorDetail } {
  if (payload === null || typeof payload !== 'object') {
    const details = sanitizeErrorValue(payload)
    return details === undefined ? {} : { details }
  }

  if (Array.isArray(payload)) {
    const details = sanitizeErrorValue(payload)
    return details === undefined ? {} : { details }
  }

  const record = payload as Record<string, unknown>
  const rawCode = record.code ?? record.error_code ?? record.type
  const code = typeof rawCode === 'string' && isSafeIdentifier(rawCode) ? rawCode : undefined
  const rawDetails = record.detail ?? record.message ?? record.error
  const details = sanitizeErrorValue(rawDetails === undefined ? payload : rawDetails)
  return details === undefined ? { code } : { code, details }
}

function clearAuthAfterUnauthorized(): void {
  clearBrowserSessionState()
  useAuthStore.getState().clearAuth()
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(SESSION_INVALIDATED_EVENT))
  }
}

async function createHttpError(response: Response, route: string): Promise<TransportError> {
  let payload: unknown
  try {
    payload = await response.clone().json()
  } catch {
    payload = undefined
  }

  const parsed = detailFromPayload(payload)
  const kind = errorKindForStatus(response.status)
  if (kind === 'UNAUTHENTICATED') clearAuthAfterUnauthorized()
  if (kind === 'FORBIDDEN' && typeof window !== 'undefined') {
    window.dispatchEvent(new Event(ACCESS_DENIED_EVENT))
  }

  const requestId = headerValue(response, 'X-Request-ID', 'X-Request-Id')
  const correlationId = headerValue(response, 'X-Correlation-ID', 'X-Correlation-Id')
  const traceId = headerValue(response, 'X-Trace-ID', 'X-Trace-Id')
  return new TransportError({
    kind,
    status: response.status,
    code: parsed.code,
    details: parsed.details,
    requestId: requestId ?? traceId,
    correlationId,
    retryAfterMs: retryAfterMs(response),
    route,
  })
}

async function requestCsrfToken(): Promise<string> {
  const generation = csrfGeneration
  const attempt = createAttemptSignal(null, CSRF_REQUEST_TIMEOUT_MS)
  const route = '/browser/csrf'
  try {
    const response = await fetch(buildApiUrl(route), {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal: attempt.signal,
    })
    if (!response.ok) throw await createHttpError(response, route)

    const payload = (await response.json()) as { csrf_token?: unknown }
    if (typeof payload.csrf_token !== 'string' || payload.csrf_token.length === 0) {
      throw new TransportError({
        kind: 'UNKNOWN',
        route,
        message: 'Browser request protection is unavailable',
      })
    }
    if (generation === csrfGeneration) csrfToken = payload.csrf_token
    return payload.csrf_token
  } catch (error) {
    throw normalizeTransportError(error, {
      route,
      timedOut: attempt.timedOut(),
    })
  } finally {
    attempt.cleanup()
    csrfRequest = null
  }
}

function waitForCsrfToken(signal: AbortSignal | null): Promise<string> {
  if (signal?.aborted) return Promise.reject(createAbortedError('/browser/csrf'))
  if (csrfToken) return Promise.resolve(csrfToken)
  if (!csrfRequest) csrfRequest = requestCsrfToken()
  if (!signal) return csrfRequest

  return new Promise<string>((resolve, reject) => {
    let settled = false
    const cleanup = (): void => {
      signal.removeEventListener('abort', abort)
    }
    const abort = (): void => {
      if (settled) return
      settled = true
      cleanup()
      reject(createAbortedError('/browser/csrf'))
    }
    signal.addEventListener('abort', abort, { once: true })
    csrfRequest
      ?.then((token) => {
        if (settled) return
        settled = true
        cleanup()
        resolve(token)
      })
      .catch((error: unknown) => {
        if (settled) return
        settled = true
        cleanup()
        reject(normalizeTransportError(error, { route: '/browser/csrf' }))
      })
  })
}

export function getApiHeaders(contentType = true): Record<string, string> {
  return contentType ? { 'Content-Type': 'application/json' } : {}
}

export function clearBrowserSessionState(): void {
  csrfToken = null
  csrfGeneration += 1
  csrfRequest = null
}

export async function apiFetch(input: string, init?: ApiFetchOptions): Promise<Response> {
  const route = input
  const url = buildApiUrl(input)
  const {
    skip401Redirect = false,
    skipCsrf = false,
    timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
    retry,
    idempotencyKey: rawIdempotencyKey,
    correlationId: rawCorrelationId,
    signal: callerSignal,
    headers: inputHeaders,
    ...requestInit
  } = init ?? {}
  // The old option is intentionally retained as a source-compatible no-op: route transitions are
  // owned by the auth/router layer, which avoids redirect loops for both frontend entry points.
  void skip401Redirect

  const method = String(requestInit.method || 'GET').toUpperCase()
  const idempotencyKey = validateOptionalIdentifier(rawIdempotencyKey, 'idempotencyKey')
  const correlationId = validateOptionalIdentifier(rawCorrelationId, 'correlationId')
  const retryPolicy = normalizeRetryPolicy(method, retry, idempotencyKey)
  let csrf: string | null = null

  if (!skipCsrf && !SAFE_METHODS.has(method)) {
    csrf = await waitForCsrfToken(callerSignal ?? null)
  }

  const headers = buildHeaders(inputHeaders, requestInit.body, csrf, idempotencyKey, correlationId)
  const maxAttempts = retryPolicy?.maxAttempts ?? 1
  let attemptNumber = 1

  while (attemptNumber <= maxAttempts) {
    if (callerSignal?.aborted) throw createAbortedError(route)
    const attempt = createAttemptSignal(callerSignal ?? null, timeoutMs)
    try {
      const response = await fetch(url, {
        ...requestInit,
        method,
        credentials: 'include',
        headers,
        signal: attempt.signal,
      })

      if (response.ok) return response

      const retryAfter = retryAfterMs(response)
      if (
        retryPolicy &&
        attemptNumber < maxAttempts &&
        SAFE_METHODS.has(method) &&
        isRetryableStatus(response.status)
      ) {
        await waitWithAbort(
          retryDelayMs(retryPolicy, attemptNumber, retryAfter),
          callerSignal ?? null,
          route
        )
        attemptNumber += 1
        continue
      }

      if (
        retryPolicy &&
        attemptNumber < maxAttempts &&
        !SAFE_METHODS.has(method) &&
        idempotencyKey !== undefined &&
        isRetryableStatus(response.status)
      ) {
        await waitWithAbort(
          retryDelayMs(retryPolicy, attemptNumber, retryAfter),
          callerSignal ?? null,
          route
        )
        attemptNumber += 1
        continue
      }

      throw await createHttpError(response, route)
    } catch (error) {
      const normalized = normalizeTransportError(error, {
        route,
        signal: callerSignal ?? undefined,
        timedOut: attempt.timedOut(),
      })
      if (retryPolicy && attemptNumber < maxAttempts && isRetryableTransportError(normalized)) {
        await waitWithAbort(retryDelayMs(retryPolicy, attemptNumber), callerSignal ?? null, route)
        attemptNumber += 1
        continue
      }
      throw normalized
    } finally {
      attempt.cleanup()
    }
  }

  throw new TransportError({ kind: 'UNKNOWN', route })
}

export async function apiFetchJson<T>(input: string, init?: ApiFetchOptions): Promise<T> {
  const response = await apiFetch(input, init)
  if (response.status === 204) return undefined as T
  try {
    return (await response.json()) as T
  } catch (error) {
    throw new TransportError({
      kind: 'UNKNOWN',
      status: response.status,
      route: input,
      message: 'The server returned an invalid response.',
      cause: error,
    })
  }
}
