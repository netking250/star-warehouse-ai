import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { buildAuthenticatedWebSocketUrl, useWebSocket } from './useWebSocket'

class FakeWebSocket {
  static readonly OPEN = 1
  static instances: FakeWebSocket[] = []
  readyState = 0
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: (() => void) | null = null

  constructor(public readonly url: string) {
    FakeWebSocket.instances.push(this)
  }

  send(): void {}

  close(): void {
    this.readyState = 3
    this.onclose?.()
  }
}

afterEach(() => {
  FakeWebSocket.instances = []
  useAuthStore.setState({ token: null, user: null, isAuthenticated: false })
  vi.unstubAllGlobals()
})

describe('buildAuthenticatedWebSocketUrl', () => {
  it('adds the access token without dropping existing query parameters', () => {
    expect(buildAuthenticatedWebSocketUrl('ws://localhost:8000/ws?room=admins', 'token value')).toBe(
      'ws://localhost:8000/ws?room=admins&token=token+value'
    )
  })

  it('does not create an unauthenticated websocket URL', () => {
    expect(buildAuthenticatedWebSocketUrl('ws://localhost:8000/ws', null)).toBeNull()
  })
})

describe('useWebSocket', () => {
  it('does not reconnect when an inline message callback changes identity', () => {
    vi.stubGlobal('WebSocket', FakeWebSocket)
    useAuthStore.setState({ token: 'jwt-token', isAuthenticated: true })

    const { rerender, unmount } = renderHook(
      ({ onMessage }) =>
        useWebSocket({ url: 'ws://localhost:8000/ws', onMessage }),
      { initialProps: { onMessage: vi.fn() } }
    )

    expect(FakeWebSocket.instances).toHaveLength(1)
    rerender({ onMessage: vi.fn() })
    expect(FakeWebSocket.instances).toHaveLength(1)

    unmount()
    expect(FakeWebSocket.instances).toHaveLength(1)
  })
})
