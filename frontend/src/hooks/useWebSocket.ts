import { useCallback, useEffect, useRef, useState } from 'react'
import { TransportError } from '@/lib/api'
import type { WSMessage } from '@/types'

interface UseWebSocketOptions {
  url: string
  enabled?: boolean
  onMessage?: (message: WSMessage) => void
  onError?: (error: TransportError) => void
  onClose?: (event: CloseEvent | undefined) => void
  maxReconnectAttempts?: number
  reconnectBaseDelayMs?: number
  reconnectMaxDelayMs?: number
  reconnectJitterRatio?: number
  random?: () => number
}

interface UseWebSocketResult {
  isConnected: boolean
  lastMessage: WSMessage | null
  error: TransportError | null
  sendMessage: (message: WSMessage) => void
}

const AUTHENTICATION_QUERY_KEYS = new Set(['token', 'access_token', 'jwt', 'authorization'])
const RECONNECTABLE_CLOSE_CODES = new Set([1001, 1006, 1011, 1012, 1013])
const AUTHENTICATION_CLOSE_CODES = new Set([1008, 4401, 4403])

export function buildAuthenticatedWebSocketUrl(url: string): string {
  const baseUrl = typeof window !== 'undefined' ? window.location.href : 'http://localhost/'
  const authenticatedUrl = new URL(url, baseUrl)
  if (!['ws:', 'wss:'].includes(authenticatedUrl.protocol)) {
    throw new TypeError('Browser WebSocket URLs must use ws or wss')
  }

  for (const key of [...authenticatedUrl.searchParams.keys()]) {
    if (AUTHENTICATION_QUERY_KEYS.has(key.toLowerCase())) {
      authenticatedUrl.searchParams.delete(key)
    }
  }

  const fragment = new URLSearchParams(authenticatedUrl.hash.slice(1))
  let removedFragmentCredential = false
  for (const key of [...fragment.keys()]) {
    if (AUTHENTICATION_QUERY_KEYS.has(key.toLowerCase())) {
      fragment.delete(key)
      removedFragmentCredential = true
    }
  }
  if (removedFragmentCredential) {
    authenticatedUrl.hash = fragment.toString() ? `#${fragment.toString()}` : ''
  }

  if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
    authenticatedUrl.protocol = 'wss:'
  }
  return authenticatedUrl.toString()
}

function isAuthenticationClose(event: CloseEvent | undefined): boolean {
  if (!event) return false
  if (AUTHENTICATION_CLOSE_CODES.has(event.code)) return true
  const reason = (event.reason ?? '').toLowerCase()
  return ['auth', 'forbidden', 'unauthorized', 'session', 'logout'].some((word) =>
    reason.includes(word)
  )
}

function isReconnectableClose(event: CloseEvent | undefined): boolean {
  if (!event) return true
  if (event.code === 1000 || isAuthenticationClose(event)) return false
  return RECONNECTABLE_CLOSE_CODES.has(event.code)
}

function reconnectDelay(
  attempt: number,
  baseDelayMs: number,
  maxDelayMs: number,
  jitterRatio: number,
  random: () => number
): number {
  const exponential = Math.min(maxDelayMs, baseDelayMs * 2 ** attempt)
  const jitter = exponential * jitterRatio * (random() * 2 - 1)
  return Math.max(0, Math.min(maxDelayMs, Math.round(exponential + jitter)))
}

export function useWebSocket({
  url,
  enabled = true,
  onMessage,
  onError,
  onClose,
  maxReconnectAttempts = 5,
  reconnectBaseDelayMs = 1_000,
  reconnectMaxDelayMs = 30_000,
  reconnectJitterRatio = 0.2,
  random = Math.random,
}: UseWebSocketOptions): UseWebSocketResult {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)
  const [error, setError] = useState<TransportError | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const onMessageRef = useRef(onMessage)
  const onErrorRef = useRef(onError)
  const onCloseRef = useRef(onClose)
  const shouldReconnectRef = useRef(false)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const connectRef = useRef<() => void>(() => undefined)

  const reportError = useCallback((transportError: TransportError): void => {
    setError(transportError)
    onErrorRef.current?.(transportError)
  }, [])

  const connect = useCallback(() => {
    if (!enabled) return
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return
    }

    let authenticatedUrl: string
    try {
      authenticatedUrl = buildAuthenticatedWebSocketUrl(url)
    } catch (connectError) {
      reportError(
        new TransportError({
          kind: 'UNKNOWN',
          route: url,
          message: 'The WebSocket URL is invalid.',
          cause: connectError,
        })
      )
      return
    }

    let ws: WebSocket
    try {
      // Browser WebSocket handshakes automatically include same-origin cookies and Origin.
      ws = new WebSocket(authenticatedUrl)
    } catch (connectError) {
      reportError(
        new TransportError({
          kind: 'NETWORK',
          route: url,
          message: 'The WebSocket connection failed.',
          cause: connectError,
        })
      )
      return
    }
    wsRef.current = ws

    ws.onopen = () => {
      if (wsRef.current !== ws) return
      setIsConnected(true)
      setError(null)
      reconnectAttemptsRef.current = 0
    }

    ws.onmessage = (event) => {
      if (wsRef.current !== ws) return
      if (typeof event.data !== 'string') {
        reportError(
          new TransportError({
            kind: 'UNKNOWN',
            route: url,
            message: 'The WebSocket message format is invalid.',
          })
        )
        return
      }
      try {
        const parsed: unknown = JSON.parse(event.data)
        if (
          parsed === null ||
          typeof parsed !== 'object' ||
          typeof (parsed as { type?: unknown }).type !== 'string'
        ) {
          throw new TypeError('WebSocket message has no valid type')
        }
        const message = parsed as WSMessage
        setLastMessage(message)
        onMessageRef.current?.(message)
      } catch (parseError) {
        reportError(
          new TransportError({
            kind: 'UNKNOWN',
            route: url,
            message: 'The WebSocket message format is invalid.',
            cause: parseError,
          })
        )
      }
    }

    ws.onerror = () => {
      reportError(
        new TransportError({
          kind: 'NETWORK',
          route: url,
          message: 'The WebSocket connection failed.',
        })
      )
    }

    ws.onclose = (event) => {
      if (wsRef.current !== ws) return
      wsRef.current = null
      setIsConnected(false)
      onCloseRef.current?.(event)

      const configuredMaxAttempts = Math.min(10, Math.max(0, Math.floor(maxReconnectAttempts)))
      if (
        !shouldReconnectRef.current ||
        !isReconnectableClose(event) ||
        reconnectAttemptsRef.current >= configuredMaxAttempts
      ) {
        return
      }

      const attempt = reconnectAttemptsRef.current
      reconnectAttemptsRef.current += 1
      const delay = reconnectDelay(
        attempt,
        Math.max(0, reconnectBaseDelayMs),
        Math.max(Math.max(0, reconnectBaseDelayMs), reconnectMaxDelayMs),
        Math.max(0, Math.min(0.5, reconnectJitterRatio)),
        () => Math.max(0, Math.min(1, random()))
      )
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null
        connectRef.current()
      }, delay)
    }
  }, [
    enabled,
    maxReconnectAttempts,
    random,
    reconnectBaseDelayMs,
    reconnectJitterRatio,
    reconnectMaxDelayMs,
    reportError,
    url,
  ])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    shouldReconnectRef.current = enabled
    reconnectAttemptsRef.current = 0
    if (enabled) connect()

    return () => {
      shouldReconnectRef.current = false
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (wsRef.current) {
        const socket = wsRef.current
        wsRef.current = null
        socket.close(1000, 'client disabled')
      }
      setIsConnected(false)
    }
  }, [connect, enabled])

  const sendMessage = useCallback((message: WSMessage): void => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  return {
    isConnected,
    lastMessage,
    error,
    sendMessage,
  }
}
