import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { buildAuthenticatedWebSocketUrl, useWebSocket } from './useWebSocket'

type CloseHandler = (event?: CloseEvent) => void

class FakeWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static instances: FakeWebSocket[] = []
  readyState = FakeWebSocket.CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: CloseHandler | null = null

  constructor(public readonly url: string) {
    FakeWebSocket.instances.push(this)
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }

  send(): void {}

  close(code = 1000, reason = ''): void {
    this.readyState = 3
    this.onclose?.({ code, reason } as CloseEvent)
  }

  fail(code = 1006, reason = ''): void {
    this.readyState = 3
    this.onclose?.({ code, reason } as CloseEvent)
  }

  message(value: unknown): void {
    this.onmessage?.({
      data: typeof value === 'string' ? value : JSON.stringify(value),
    } as MessageEvent)
  }
}

afterEach(() => {
  FakeWebSocket.instances = []
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('buildAuthenticatedWebSocketUrl', () => {
  it('preserves non-credential query parameters', () => {
    expect(buildAuthenticatedWebSocketUrl('ws://localhost:8000/ws?room=admins')).toBe(
      'ws://localhost:8000/ws?room=admins'
    )
  })

  it('removes every browser credential query spelling', () => {
    const url = buildAuthenticatedWebSocketUrl(
      'ws://localhost:8000/ws?token=one&access_token=two&jwt=three&authorization=four&room=admins'
    )
    expect(url).toBe('ws://localhost:8000/ws?room=admins')
  })

  it('removes credential-like fragment parameters while preserving safe fragments', () => {
    const url = buildAuthenticatedWebSocketUrl(
      'ws://localhost:8000/ws?room=admins#access_token=one&section=notifications'
    )
    expect(url).toBe('ws://localhost:8000/ws?room=admins#section=notifications')
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

  it('reconnects with bounded deterministic backoff and stops after the configured attempts', () => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeWebSocket)
    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        maxReconnectAttempts: 2,
        reconnectBaseDelayMs: 100,
        reconnectMaxDelayMs: 500,
        reconnectJitterRatio: 0,
        random: () => 0.5,
      })
    )

    FakeWebSocket.instances[0]?.fail(1006)
    vi.advanceTimersByTime(99)
    expect(FakeWebSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(FakeWebSocket.instances).toHaveLength(2)

    FakeWebSocket.instances[1]?.fail(1006)
    vi.advanceTimersByTime(199)
    expect(FakeWebSocket.instances).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(FakeWebSocket.instances).toHaveLength(3)

    FakeWebSocket.instances[2]?.fail(1006)
    vi.advanceTimersByTime(10_000)
    expect(FakeWebSocket.instances).toHaveLength(3)
  })

  it('applies deterministic jitter to the reconnect delay', () => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeWebSocket)
    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        reconnectBaseDelayMs: 100,
        reconnectJitterRatio: 0.2,
        random: () => 1,
      })
    )

    FakeWebSocket.instances[0]?.fail(1006)
    vi.advanceTimersByTime(119)
    expect(FakeWebSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(FakeWebSocket.instances).toHaveLength(2)
  })

  it.each([
    [1000, 'normal close'],
    [1008, 'Authentication failed'],
    [4401, 'unauthenticated'],
    [4403, 'forbidden'],
  ])('does not reconnect after close code %s (%s)', (code, reason) => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeWebSocket)
    renderHook(() => useWebSocket({ url: 'ws://localhost:8000/ws' }))

    FakeWebSocket.instances[0]?.fail(code, reason)
    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it('stops reconnecting when auth is disabled, avoiding a logout reconnect storm', () => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeWebSocket)
    const { rerender } = renderHook(
      ({ enabled }) => useWebSocket({ url: 'ws://localhost:8000/ws', enabled }),
      { initialProps: { enabled: true } }
    )

    FakeWebSocket.instances[0]?.fail(1006)
    rerender({ enabled: false })
    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it('parses valid messages, sends through the cookie-authenticated socket, and reports invalid data safely', () => {
    vi.stubGlobal('WebSocket', FakeWebSocket)
    const onMessage = vi.fn()
    const { result } = renderHook(() => useWebSocket({ url: 'ws://localhost:8000/ws', onMessage }))
    const socket = FakeWebSocket.instances[0]
    act(() => {
      socket?.open()
      socket?.message({ type: 'status_change' })
      socket?.message('not-json')
    })

    expect(onMessage).toHaveBeenCalledWith({ type: 'status_change' })
    expect(result.current.lastMessage).toEqual({ type: 'status_change' })
    expect(result.current.error?.kind).toBe('UNKNOWN')
    expect(result.current.isConnected).toBe(true)
  })
})
