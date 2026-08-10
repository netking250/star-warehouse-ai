import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuthStore } from '@/stores/auth'
import type { WSMessage } from '@/types'

interface UseWebSocketOptions {
  url: string
  enabled?: boolean
  onMessage?: (message: WSMessage) => void
}

interface UseWebSocketResult {
  isConnected: boolean
  lastMessage: WSMessage | null
  sendMessage: (message: WSMessage) => void
}

export function buildAuthenticatedWebSocketUrl(url: string, token: string | null): string | null {
  if (!token) return null
  const authenticatedUrl = new URL(url)
  authenticatedUrl.searchParams.set('token', token)
  return authenticatedUrl.toString()
}

export function useWebSocket({
  url,
  enabled = true,
  onMessage,
}: UseWebSocketOptions): UseWebSocketResult {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const onMessageRef = useRef(onMessage)
  const shouldReconnectRef = useRef(false)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const maxReconnectAttempts = 5

  const connect = useCallback(() => {
    if (!enabled || wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const authenticatedUrl = buildAuthenticatedWebSocketUrl(url, useAuthStore.getState().token)
      if (!authenticatedUrl) return

      const ws = new WebSocket(authenticatedUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        reconnectAttemptsRef.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const rawData: unknown = event.data
          if (typeof rawData !== 'string') {
            throw new TypeError('WebSocket message must be text')
          }
          const parsed = JSON.parse(rawData) as WSMessage
          setLastMessage(parsed)
          onMessageRef.current?.(parsed)
        } catch (err) {
          console.error('[useWebSocket] Failed to parse message:', err)
        }
      }

      ws.onerror = (err) => {
        console.error('[useWebSocket] Connection error:', err)
      }

      ws.onclose = () => {
        setIsConnected(false)
        wsRef.current = null

        if (shouldReconnectRef.current && reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * 2 ** reconnectAttemptsRef.current, 30000)
          reconnectAttemptsRef.current += 1
          reconnectTimerRef.current = setTimeout(() => {
            connect()
          }, delay)
        }
      }
    } catch (err) {
      console.error('[useWebSocket] Failed to connect:', err)
    }
  }, [url, enabled])

  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    shouldReconnectRef.current = enabled
    if (enabled) {
      connect()
    }

    return () => {
      shouldReconnectRef.current = false
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, enabled])

  const sendMessage = useCallback((message: WSMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  return {
    isConnected,
    lastMessage,
    sendMessage,
  }
}
