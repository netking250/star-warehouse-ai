import { useCallback, useEffect, useRef, useState } from 'react'
import type { Message, MessageMetadata } from '@/types'
import { apiFetch, isTransportError, normalizeTransportError, TransportError } from '@/lib/api'
import { readSseData } from '@/lib/streaming'

interface FeedbackRequest {
  thread_id: string
  message_index: number
  sentiment: 'up' | 'down'
  comment?: string
  category?: string
  agent_type?: string
  confidence_score?: number
}

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  role: 'assistant',
  content:
    '你好，我是星仓 AI，很高兴为你服务。无论是订单、物流、退换货，还是商品选购，我都可以帮你快速处理。',
  timestamp: new Date(),
}

interface StreamPayload {
  token?: unknown
  type?: unknown
  event?: unknown
  error?: unknown
  run_id?: unknown
  [key: string]: unknown
}

interface ActiveGeneration {
  controller: AbortController
  assistantMessageId: string
  threadId: string
  runId: string | null
  logicalCancellationRequested: boolean
}

interface UseChatReturn {
  messages: Message[]
  isLoading: boolean
  sendMessage: (content: string, threadId: string) => Promise<void>
  cancelGeneration: () => Promise<void>
  submitFeedback: (
    messageId: string,
    sentiment: 'up' | 'down',
    threadId: string,
    messageIndex: number,
    category?: string,
    comment?: string
  ) => Promise<void>
  resetMessages: () => void
}

function createIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

function isStreamPayload(value: unknown): value is StreamPayload {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function mergeMetadata(
  current: MessageMetadata | undefined,
  payload: StreamPayload
): MessageMetadata {
  const confidenceSignals =
    payload.confidence_signals !== null && typeof payload.confidence_signals === 'object'
      ? (payload.confidence_signals as Record<string, unknown>)
      : current?.confidence_signals
  return {
    ...current,
    confidence_score:
      typeof payload.confidence_score === 'number'
        ? payload.confidence_score
        : current?.confidence_score,
    confidence_signals: confidenceSignals,
    needs_human_transfer:
      typeof payload.needs_human_transfer === 'boolean'
        ? payload.needs_human_transfer
        : current?.needs_human_transfer,
    transfer_reason: stringValue(payload.transfer_reason) ?? current?.transfer_reason,
    audit_level: stringValue(payload.audit_level) ?? current?.audit_level,
    current_agent: stringValue(payload.current_agent) ?? current?.current_agent,
    trace_id: stringValue(payload.trace_id) ?? current?.trace_id,
  }
}

function chatFailureMessage(error: unknown): string {
  if (isTransportError(error)) {
    switch (error.kind) {
      case 'CONFLICT':
        return '已有一条消息正在处理中，请稍后再试。'
      case 'VALIDATION':
        return '消息内容无效，请检查后重试。'
      case 'RATE_LIMITED':
        return '请求过于频繁，请稍后再试。'
      case 'TIMEOUT':
        return '服务响应超时，请稍后重试。'
      case 'UNAUTHENTICATED':
        return '登录状态已失效，请重新登录。'
      default:
        return '抱歉，服务暂时不可用，请稍后重试。'
    }
  }
  return '抱歉，服务暂时不可用，请稍后重试。'
}

function markAssistant(
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
  assistantMessageId: string,
  update: (message: Message) => Message
): void {
  setMessages((previous) =>
    previous.map((message) => (message.id === assistantMessageId ? update(message) : message))
  )
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [isLoading, setIsLoading] = useState(false)
  const activeGenerationRef = useRef<ActiveGeneration | null>(null)

  const cancelGeneration = useCallback(async (): Promise<void> => {
    const generation = activeGenerationRef.current
    if (!generation) return

    generation.logicalCancellationRequested = true
    generation.controller.abort()
    if (generation.runId) {
      try {
        await apiFetch(
          `/conversations/${encodeURIComponent(generation.threadId)}/runs/${encodeURIComponent(generation.runId)}/cancel`,
          {
            method: 'POST',
            timeoutMs: 10_000,
            retry: false,
          }
        )
      } catch {
        // Local cancellation remains quiet; the durable endpoint owns logical cancellation.
      }
    }
    markAssistant(setMessages, generation.assistantMessageId, (message) => ({
      ...message,
      content: message.content || '已停止生成。',
      isStreaming: false,
    }))
    setIsLoading(false)
  }, [])

  useEffect(() => {
    return () => {
      if (activeGenerationRef.current) void cancelGeneration()
    }
  }, [cancelGeneration])

  const sendMessage = useCallback(
    async (content: string, threadId: string): Promise<void> => {
      if (!content.trim() || isLoading || activeGenerationRef.current) return

      const userMessage: Message = {
        id: `user_${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date(),
      }
      const assistantMessageId = `assistant_${Date.now()}`
      const generation: ActiveGeneration = {
        controller: new AbortController(),
        assistantMessageId,
        threadId,
        runId: null,
        logicalCancellationRequested: false,
      }
      activeGenerationRef.current = generation

      setMessages((previous) => [
        ...previous,
        userMessage,
        {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          isStreaming: true,
        },
      ])
      setIsLoading(true)

      let fullContent = ''
      let metadata: MessageMetadata | undefined
      let turnAccepted = false
      let terminal: 'success' | 'failure' | 'cancelled' | null = null

      const acceptTerminal = (
        kind: 'success' | 'failure' | 'cancelled',
        message?: string
      ): void => {
        if (terminal !== null) return
        terminal = kind
        markAssistant(setMessages, assistantMessageId, (current) => ({
          ...current,
          content:
            kind === 'failure'
              ? message || chatFailureMessage(undefined)
              : kind === 'cancelled'
                ? current.content || '已停止生成。'
                : current.content,
          isStreaming: false,
          metadata,
        }))
      }

      try {
        const response = await apiFetch('/chat', {
          method: 'POST',
          body: JSON.stringify({ question: userMessage.content, thread_id: threadId }),
          idempotencyKey: createIdempotencyKey(),
          timeoutMs: 60_000,
          retry: false,
          signal: generation.controller.signal,
        })

        for await (const data of readSseData(response.body, {
          signal: generation.controller.signal,
          route: '/chat',
        })) {
          if (data === '[DONE]') {
            if (terminal === null) acceptTerminal('success')
            continue
          }

          let parsed: unknown
          try {
            parsed = JSON.parse(data)
          } catch (parseError) {
            throw new TransportError({
              kind: 'UNKNOWN',
              route: '/chat',
              message: 'The streaming event format is invalid.',
              cause: parseError,
            })
          }
          if (!isStreamPayload(parsed)) {
            throw new TransportError({
              kind: 'UNKNOWN',
              route: '/chat',
              message: 'The streaming event format is invalid.',
            })
          }

          const runtimeEvent = stringValue(parsed.event)
          if (parsed.type === 'runtime' && runtimeEvent) {
            if (runtimeEvent === 'TURN_ACCEPTED') {
              if (terminal !== null || turnAccepted) continue
              turnAccepted = true
              generation.runId = stringValue(parsed.run_id)
              continue
            }
            if (runtimeEvent === 'RUN_COMPLETED') {
              acceptTerminal('success')
              continue
            }
            if (runtimeEvent === 'RUN_CANCELLED') {
              acceptTerminal('cancelled')
              continue
            }
            if (runtimeEvent === 'RUN_FAILED') {
              acceptTerminal('failure')
              continue
            }
          }

          const streamError = stringValue(parsed.error)
          if (streamError) {
            if (terminal === null) acceptTerminal('failure')
            continue
          }

          if (parsed.type === 'metadata') {
            metadata = mergeMetadata(metadata, parsed)
            markAssistant(setMessages, assistantMessageId, (current) => ({
              ...current,
              metadata,
            }))
            continue
          }

          if (terminal !== null) continue

          const token = stringValue(parsed.token)
          if (token !== null) {
            fullContent += token
            markAssistant(setMessages, assistantMessageId, (current) => ({
              ...current,
              content: fullContent,
              metadata,
            }))
          }
        }

        if (terminal === null) {
          throw new TransportError({
            kind: 'NETWORK',
            route: '/chat',
            message: 'The streaming connection ended before completion.',
          })
        }
      } catch (error) {
        const transportError = normalizeTransportError(error, {
          route: '/chat',
          signal: generation.controller.signal,
        })
        if (generation.logicalCancellationRequested || transportError.kind === 'ABORTED') {
          acceptTerminal('cancelled')
        } else if (terminal === null) {
          acceptTerminal('failure', chatFailureMessage(transportError))
        }
      } finally {
        if (activeGenerationRef.current === generation) activeGenerationRef.current = null
        setIsLoading(false)
      }
    },
    [isLoading]
  )

  const resetMessages = useCallback(() => {
    setMessages([WELCOME_MESSAGE])
  }, [])

  const submitFeedback = useCallback(
    async (
      messageId: string,
      sentiment: 'up' | 'down',
      threadId: string,
      messageIndex: number,
      category?: string,
      comment?: string
    ): Promise<void> => {
      try {
        const msg = messages.find((message) => message.id === messageId)
        const feedbackData: FeedbackRequest = {
          thread_id: threadId,
          message_index: messageIndex,
          sentiment,
          ...(category && { category }),
          ...(comment && { comment }),
          ...(msg?.metadata?.current_agent && { agent_type: msg.metadata.current_agent }),
          ...(msg?.metadata?.confidence_score !== undefined && {
            confidence_score: msg.metadata.confidence_score,
          }),
        }

        await apiFetch('/feedback', {
          method: 'POST',
          body: JSON.stringify(feedbackData),
          retry: false,
        })

        setMessages((previous) =>
          previous.map((message) =>
            message.id === messageId ? { ...message, feedbackSentiment: sentiment } : message
          )
        )
      } catch {
        // Feedback failure is non-blocking and intentionally does not expose a raw response.
      }
    },
    [messages]
  )

  return {
    messages,
    isLoading,
    sendMessage,
    cancelGeneration,
    submitFeedback,
    resetMessages,
  }
}
