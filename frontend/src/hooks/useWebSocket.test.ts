import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
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
  vi.unstubAllGlobals()
})

describe('buildAuthenticatedWebSocketUrl', () => {
  it('preserves the URL without adding a browser credential', () => {
    expect(buildAuthenticatedWebSocketUrl('ws://localhost:8000/ws?room=admins')).toBe(
      'ws://localhost:8000/ws?room=admins'
    )
  })

  it('never emits token query parameters', () => {
    expect(buildAuthenticatedWebSocketUrl('ws://localhost:8000/ws')).not.toContain('token=')
  })
})

describe('useWebSocket', () => {
  it('does not reconnect when an inline message callback changes identity', () => {
    vi.stubGlobal('WebSocket', FakeWebSocket)

    const { rerender, unmount } = renderHook(
      ({ onMessage }) => useWebSocket({ url: 'ws://localhost:8000/ws', onMessage }),
      { initialProps: { onMessage: vi.fn() } }
    )

    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(FakeWebSocket.instances[0]?.url).toBe('ws://localhost:8000/ws')
    rerender({ onMessage: vi.fn() })
    expect(FakeWebSocket.instances).toHaveLength(1)

    unmount()
    expect(FakeWebSocket.instances).toHaveLength(1)
  })
})
