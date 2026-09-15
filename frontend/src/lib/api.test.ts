import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, clearBrowserSessionState, isTransportError, TransportError } from './api'
import { useAuthStore } from '@/stores/auth'

const authenticatedUser = {
  user_id: 7,
  username: 'transport-user',
  role: 'USER' as const,
}

function response(status: number, payload: unknown = {}, headers?: HeadersInit): Response {
  return new Response(status === 204 ? null : JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

beforeEach(() => {
  useAuthStore.setState({ user: authenticatedUser, isAuthenticated: true, isInitialized: true })
})

afterEach(() => {
  clearBrowserSessionState()
  useAuthStore.setState({ user: null, isAuthenticated: false, isInitialized: false })
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('apiFetch browser session transport', () => {
  it('sends cookies and attaches an in-memory CSRF token to unsafe requests', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response(200, { csrf_token: 'session-bound-csrf' }))
      .mockResolvedValueOnce(response(204))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/logout', { method: 'POST', retry: false })

    const [csrfInput, csrfInit] = fetchMock.mock.calls[0] ?? []
    const [logoutInput, logoutInit] = fetchMock.mock.calls[1] ?? []
    expect(typeof csrfInput === 'string' && csrfInput.endsWith('/browser/csrf')).toBe(true)
    expect(csrfInit?.credentials).toBe('include')
    expect(typeof logoutInput === 'string' && logoutInput.endsWith('/logout')).toBe(true)
    expect(logoutInit?.credentials).toBe('include')
    expect(new Headers(logoutInit?.headers).get('X-CSRF-Token')).toBe('session-bound-csrf')
  })

  it('does not attach CSRF to safe session bootstrap requests', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response(200, {}))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/me', { method: 'GET', retry: false })

    const [input, init] = fetchMock.mock.calls[0] ?? []
    expect(typeof input === 'string' && input.endsWith('/me')).toBe(true)
    expect(init?.credentials).toBe('include')
    expect(new Headers(init?.headers).has('X-CSRF-Token')).toBe(false)
  })

  it('rejects authentication credentials in API URLs or caller headers', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response(200, {}))
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      apiFetch('/resource?access_token=should-not-leak', { retry: false })
    ).rejects.toThrow('authentication query parameters')
    await expect(
      apiFetch('/resource', {
        headers: { Authorization: 'Bearer should-not-leak' },
        retry: false,
      })
    ).rejects.toThrow('does not accept Authorization headers')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('normalizes 401 and clears the in-memory auth state without redirecting', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response(401, { detail: 'expired' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiFetch('/me', { retry: false })).rejects.toMatchObject({
      kind: 'UNAUTHENTICATED',
      status: 401,
    })
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('preserves authenticated state for 403 responses', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(response(403, { code: 'FORBIDDEN_ACTION', detail: 'denied' }))
    vi.stubGlobal('fetch', fetchMock)

    const errorPromise = apiFetch('/admin/tasks', { retry: false })
    await expect(errorPromise).rejects.toMatchObject({
      kind: 'FORBIDDEN',
      status: 403,
      code: 'FORBIDDEN_ACTION',
      details: 'denied',
    })
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })

  it('keeps structured conflict and validation details in the normalized model', async () => {
    const conflictFetch = vi
      .fn<typeof fetch>()
      .mockResolvedValue(response(409, { code: 'RUN_BUSY', detail: 'run already active' }))
    vi.stubGlobal('fetch', conflictFetch)
    await expect(
      apiFetch('/chat', { method: 'POST', skipCsrf: true, retry: false })
    ).rejects.toMatchObject({
      kind: 'CONFLICT',
      status: 409,
      code: 'RUN_BUSY',
      details: 'run already active',
    })

    const validationFetch = vi.fn<typeof fetch>().mockResolvedValue(
      response(422, {
        detail: [{ loc: ['body', 'question'], msg: 'required', type: 'value_error' }],
      })
    )
    vi.stubGlobal('fetch', validationFetch)
    await expect(
      apiFetch('/chat', { method: 'POST', skipCsrf: true, retry: false })
    ).rejects.toMatchObject({
      kind: 'VALIDATION',
      status: 422,
      details: [{ loc: ['body', 'question'], msg: 'required', type: 'value_error' }],
    })
  })

  it('normalizes a network failure distinctly from a caller abort', async () => {
    const networkFetch = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'))
    vi.stubGlobal('fetch', networkFetch)
    await expect(apiFetch('/health', { retry: false })).rejects.toMatchObject({ kind: 'NETWORK' })

    const controller = new AbortController()
    const abortFetch = vi.fn<typeof fetch>().mockImplementation(
      (_input, init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            'abort',
            () => reject(new DOMException('aborted', 'AbortError')),
            {
              once: true,
            }
          )
        })
    )
    vi.stubGlobal('fetch', abortFetch)
    const aborted = apiFetch('/health', {
      retry: { maxAttempts: 3, baseDelayMs: 0, jitterRatio: 0 },
      signal: controller.signal,
    })
    controller.abort()
    await expect(aborted).rejects.toMatchObject({ kind: 'ABORTED' })
    expect(abortFetch).toHaveBeenCalledTimes(1)
  })

  it('normalizes a request deadline as TIMEOUT', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(
      (_input, init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            'abort',
            () => reject(new DOMException('timeout', 'AbortError')),
            {
              once: true,
            }
          )
        })
    )
    vi.stubGlobal('fetch', fetchMock)

    const pending = apiFetch('/slow', { timeoutMs: 25, retry: false })
    const assertion = expect(pending).rejects.toMatchObject({ kind: 'TIMEOUT' })
    await vi.advanceTimersByTimeAsync(25)
    await assertion
  })

  it('performs a bounded safe-read retry for a transient response', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response(503, { detail: 'temporary' }))
      .mockResolvedValueOnce(response(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await apiFetch('/status', {
      retry: { maxAttempts: 2, baseDelayMs: 0, maxDelayMs: 10, jitterRatio: 0 },
    })
    expect(result.status).toBe(200)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it.each([401, 403, 422])('does not retry HTTP status %s', async (status) => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(response(status, { detail: 'no retry' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      apiFetch('/resource', {
        retry: { maxAttempts: 3, baseDelayMs: 0, jitterRatio: 0 },
      })
    ).rejects.toBeInstanceOf(TransportError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('does not retry mutations without an explicit idempotency key', async () => {
    const csrfFetch = vi.fn<typeof fetch>().mockResolvedValue(response(200, { csrf_token: 'csrf' }))
    const mutationFetch = vi
      .fn<typeof fetch>()
      .mockResolvedValue(response(503, { detail: 'temporary' }))
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input, init) => {
      if (typeof input === 'string' && input.endsWith('/browser/csrf'))
        return csrfFetch(input, init)
      return mutationFetch(input, init)
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      apiFetch('/resource', {
        method: 'POST',
        retry: { maxAttempts: 3, baseDelayMs: 0, jitterRatio: 0 },
      })
    ).rejects.toMatchObject({ kind: 'SERVER' })
    expect(mutationFetch).toHaveBeenCalledTimes(1)
  })

  it('reuses one supplied idempotency key if a mutation opts into retry', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response(503, { detail: 'temporary' }))
      .mockResolvedValueOnce(response(204))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/chat', {
      method: 'POST',
      skipCsrf: true,
      idempotencyKey: 'chat-operation-1',
      retry: { maxAttempts: 2, baseDelayMs: 0, jitterRatio: 0 },
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get('Idempotency-Key')).toBe(
      'chat-operation-1'
    )
    expect(new Headers(fetchMock.mock.calls[1]?.[1]?.headers).get('Idempotency-Key')).toBe(
      'chat-operation-1'
    )
  })

  it('captures safe correlation metadata and bounded Retry-After information', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      response(
        429,
        { code: 'RATE_LIMIT', detail: 'slow down' },
        {
          'Retry-After': '60',
          'X-Correlation-ID': 'corr-123',
          'X-Request-ID': 'request-123',
        }
      )
    )
    vi.stubGlobal('fetch', fetchMock)

    const error = await apiFetch('/rate-limited', { retry: false }).catch((value: unknown) => value)
    expect(isTransportError(error)).toBe(true)
    expect(error).toMatchObject({
      kind: 'RATE_LIMITED',
      code: 'RATE_LIMIT',
      correlationId: 'corr-123',
      requestId: 'request-123',
      retryAfterMs: 5_000,
    })
  })
})
