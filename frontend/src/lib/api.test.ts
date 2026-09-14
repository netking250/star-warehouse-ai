import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, clearBrowserSessionState } from './api'

afterEach(() => {
  clearBrowserSessionState()
  vi.restoreAllMocks()
})

describe('apiFetch browser session transport', () => {
  it('sends cookies and attaches an in-memory CSRF token to unsafe requests', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrf_token: 'session-bound-csrf' }), { status: 200 })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/logout', { method: 'POST', skip401Redirect: true })

    const [csrfInput, csrfInit] = fetchMock.mock.calls[0] ?? []
    const [logoutInput, logoutInit] = fetchMock.mock.calls[1] ?? []
    expect(typeof csrfInput === 'string' && csrfInput.endsWith('/browser/csrf')).toBe(true)
    expect(csrfInit?.credentials).toBe('include')
    expect(typeof logoutInput === 'string' && logoutInput.endsWith('/logout')).toBe(true)
    expect(logoutInit?.credentials).toBe('include')
    expect(new Headers(logoutInit?.headers).get('X-CSRF-Token')).toBe('session-bound-csrf')
  })

  it('does not attach CSRF to safe session bootstrap requests', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/me', { method: 'GET', skip401Redirect: true })

    const [input, init] = fetchMock.mock.calls[0] ?? []
    expect(typeof input === 'string' && input.endsWith('/me')).toBe(true)
    expect(init?.credentials).toBe('include')
    expect(new Headers(init?.headers).has('X-CSRF-Token')).toBe(false)
  })
})
