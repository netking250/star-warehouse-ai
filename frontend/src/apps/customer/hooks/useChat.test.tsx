import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearBrowserSessionState } from '@/lib/api'
import { useChat } from './useChat'

function sseBody(events: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) controller.enqueue(encoder.encode(`data: ${event}\n\n`))
      controller.close()
    },
  })
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  return input.url
}

function installChatFetch(
  body: ReadableStream<Uint8Array>
): ReturnType<typeof vi.fn<typeof fetch>> {
  return vi.fn<typeof fetch>().mockImplementation((input, init) => {
    const url = requestUrl(input)
    if (url.endsWith('/browser/csrf')) {
      return Promise.resolve(
        new Response(JSON.stringify({ csrf_token: 'chat-csrf' }), { status: 200 })
      )
    }
    if (url.endsWith('/chat')) {
      return Promise.resolve(
        new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
      )
    }
    if (url.includes('/cancel')) return Promise.resolve(new Response(null, { status: 204 }))
    return Promise.reject(new Error(`Unexpected request: ${url} ${init?.method ?? 'GET'}`))
  })
}

beforeEach(() => {
  clearBrowserSessionState()
})

afterEach(() => {
  clearBrowserSessionState()
  vi.restoreAllMocks()
})

describe('useChat streaming transport', () => {
  it('accepts TURN_ACCEPTED and terminal events once, ignoring late duplicate data', async () => {
    const fetchMock = installChatFetch(
      sseBody([
        '{"type":"runtime","event":"TURN_ACCEPTED","run_id":"run-1"}',
        '{"type":"runtime","event":"TURN_ACCEPTED","run_id":"run-1"}',
        '{"token":"Hello"}',
        '{"type":"runtime","event":"RUN_COMPLETED","run_id":"run-1"}',
        '{"type":"metadata","confidence_score":0.9}',
        '{"token":"late"}',
        '[DONE]',
        '[DONE]',
      ])
    )
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useChat())

    await act(async () => result.current.sendMessage('hello', 'thread-1'))

    const assistant = result.current.messages[result.current.messages.length - 1]
    expect(assistant?.content).toBe('Hello')
    expect(assistant?.isStreaming).toBe(false)
    expect(assistant?.metadata?.confidence_score).toBe(0.9)
    expect(
      fetchMock.mock.calls.filter(([input]) => requestUrl(input).endsWith('/chat'))
    ).toHaveLength(1)

    const chatCall = fetchMock.mock.calls.find(([input]) => requestUrl(input).endsWith('/chat'))
    expect(new Headers(chatCall?.[1]?.headers).get('X-CSRF-Token')).toBe('chat-csrf')
    expect(new Headers(chatCall?.[1]?.headers).get('Idempotency-Key')).toMatch(
      /^chat|^[0-9a-f-]{36}$/i
    )
  })

  it('shows one terminal failure and ignores duplicate terminal events and late tokens', async () => {
    const fetchMock = installChatFetch(
      sseBody([
        '{"token":"partial"}',
        '{"type":"runtime","event":"RUN_FAILED"}',
        '{"type":"runtime","event":"RUN_FAILED"}',
        '{"token":"late"}',
        '[DONE]',
      ])
    )
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useChat())

    await act(async () => result.current.sendMessage('hello', 'thread-1'))

    const assistant = result.current.messages[result.current.messages.length - 1]
    expect(assistant?.isStreaming).toBe(false)
    expect(assistant?.content).not.toContain('late')
    expect(assistant?.content).not.toBe('partial')
  })

  it('normalizes an incomplete stream as a visible failure', async () => {
    const fetchMock = installChatFetch(sseBody(['{"token":"partial"}']))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useChat())

    await act(async () => result.current.sendMessage('hello', 'thread-1'))

    const assistant = result.current.messages[result.current.messages.length - 1]
    expect(assistant?.isStreaming).toBe(false)
    expect(assistant?.content).not.toBe('partial')
    expect(assistant?.content).toBeTruthy()
  })

  it('aborts the local stream and calls T12 logical cancellation once the run is accepted', async () => {
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"type":"runtime","event":"TURN_ACCEPTED","run_id":"run-1"}\n\n')
        )
      },
    })
    const fetchMock = installChatFetch(body)
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useChat())
    let sendPromise: Promise<void> | undefined

    await act(async () => {
      sendPromise = result.current.sendMessage('hello', 'thread-1')
      await waitFor(() =>
        expect(fetchMock.mock.calls.some(([input]) => requestUrl(input).endsWith('/chat'))).toBe(
          true
        )
      )
      for (let index = 0; index < 5; index += 1) await Promise.resolve()
    })

    await act(async () => result.current.cancelGeneration())
    await sendPromise

    const cancelCalls = fetchMock.mock.calls.filter(([input]) =>
      requestUrl(input).includes('/cancel')
    )
    expect(cancelCalls).toHaveLength(1)
    expect(requestUrl(cancelCalls[0]?.[0] as RequestInfo | URL)).toContain(
      '/conversations/thread-1/runs/run-1/cancel'
    )
    expect(result.current.messages[result.current.messages.length - 1]?.isStreaming).toBe(false)
  })
})
