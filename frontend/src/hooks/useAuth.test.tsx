import type { PropsWithChildren } from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearBrowserSessionState } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { useAuth } from './useAuth'

const session = {
  user_id: 42,
  username: 'browser-user',
  email: 'browser@example.com',
  full_name: 'Browser User',
  is_admin: false,
  tenant_id: 'default',
  roles: ['customer'],
  scopes: ['chat.use'],
  session_id: 'browser-session',
}

function createWrapper(): React.FC<PropsWithChildren> {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

beforeEach(() => {
  clearBrowserSessionState()
  useAuthStore.setState({ user: null, isAuthenticated: false, isInitialized: false })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useAuth server-authoritative state', () => {
  it('restores authenticated state from the current-user endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(session), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    renderHook(() => useAuth(), { wrapper: createWrapper() })

    await waitFor(() => expect(useAuthStore.getState().isAuthenticated).toBe(true))
    expect(useAuthStore.getState().user?.user_id).toBe(42)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/me'),
      expect.objectContaining({ credentials: 'include' })
    )
  })

  it('logs out through the server then clears in-memory identity state', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify(session), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrf_token: 'logout-csrf' }), { status: 200 })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() })
    await waitFor(() => expect(useAuthStore.getState().isAuthenticated).toBe(true))

    await act(async () => result.current.logout())

    expect(
      fetchMock.mock.calls.some(([input]) => typeof input === 'string' && input.endsWith('/logout'))
    ).toBe(true)
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().user).toBeNull()
  })
})
