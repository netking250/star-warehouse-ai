import { forwardRef } from 'react'
import {
  Loader2,
  PackageSearch,
  ReceiptText,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Truck,
  User,
} from 'lucide-react'
import { BrandMark } from '@/components/brand/StarWarehouseLogo'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { Message } from '@/types'
import { FeedbackWidget } from './FeedbackWidget'

interface ChatMessageListProps {
  messages: Message[]
  isLoading: boolean
  onFeedback?: (
    messageId: string,
    sentiment: 'up' | 'down',
    messageIndex: number,
    category?: string,
    comment?: string
  ) => void
  onQuickTask?: (prompt: string) => void
}

const WELCOME_TASKS = [
  {
    title: '查询我的订单',
    description: '查看近期订单与当前状态',
    icon: PackageSearch,
    prompt: '帮我查询一下最近的订单状态',
  },
  {
    title: '物流到哪了',
    description: '了解订单的最新物流进度',
    icon: Truck,
    prompt: '帮我查询一下订单的物流进度',
  },
  {
    title: '退换货政策',
    description: '了解办理条件与服务边界',
    icon: ReceiptText,
    prompt: '请介绍一下退换货政策和办理条件',
  },
  {
    title: '商品选购建议',
    description: '根据真实需求梳理选择方向',
    icon: Sparkles,
    prompt: '我想选购商品，请根据我的需求给一些建议',
  },
]

function AssistantIdentity(): React.ReactElement {
  return (
    <div className="brand-mark-shell grid h-8 w-8 shrink-0 place-items-center rounded-[var(--radius-md)]">
      <BrandMark className="h-6 w-6" />
    </div>
  )
}

/** Render the active customer conversation and its service states. */
export const ChatMessageList = forwardRef<HTMLDivElement, ChatMessageListProps>(
  ({ messages, isLoading, onFeedback, onQuickTask }, ref) => {
    const conversationMessages = messages.filter((message) => message.id !== 'welcome')
    let assistantMessageCount = messages.some((message) => message.id === 'welcome') ? 1 : 0

    return (
      <ScrollArea className="relative z-10 flex-1" ref={ref}>
        <div className="mx-auto w-full max-w-[56rem] px-4 pb-10 pt-6 sm:px-8 sm:pb-14 sm:pt-10">
          {conversationMessages.length === 0 && (
            <section className="page-enter mx-auto flex min-h-[min(58vh,35rem)] max-w-[48rem] flex-col justify-center py-8 sm:py-12">
              <div className="mb-7 flex items-center gap-4">
                <div className="brand-mark-shell grid h-14 w-14 shrink-0 place-items-center rounded-[var(--radius-lg)]">
                  <BrandMark className="h-11 w-11" />
                </div>
                <div>
                  <p className="text-caption uppercase tracking-[0.18em] text-primary">
                    星仓 AI · 智能服务
                  </p>
                  <h2 className="mt-1.5 text-2xl font-semibold tracking-[-0.035em] text-foreground sm:text-[2rem]">
                    今天需要处理什么？
                  </h2>
                </div>
              </div>
              <p className="max-w-xl text-sm leading-7 text-muted-foreground sm:text-[15px]">
                我可以协助查询订单与物流、说明售后政策，并结合企业知识梳理商品选择。
              </p>
              <div className="mt-7 grid gap-3 sm:grid-cols-2">
                {WELCOME_TASKS.map(({ title, description, icon: Icon, prompt }) => (
                  <button
                    key={title}
                    type="button"
                    onClick={() => onQuickTask?.(prompt)}
                    disabled={isLoading}
                    className="group flex min-h-24 items-start gap-3 rounded-[var(--radius-lg)] border border-border-subtle bg-surface/72 p-4 text-left shadow-sm transition-[transform,border-color,background-color,box-shadow] duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:bg-surface-elevated hover:shadow-md disabled:pointer-events-none disabled:opacity-50"
                  >
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-[var(--radius-md)] bg-primary/8 text-primary transition-colors group-hover:bg-primary/12">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span>
                      <span className="block text-sm font-semibold text-foreground">{title}</span>
                      <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                        {description}
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            </section>
          )}

          <div className="space-y-8" aria-live="polite" aria-busy={isLoading}>
            {conversationMessages.map((message) => {
              const isAssistant = message.role === 'assistant'
              const currentMessageIndex = isAssistant ? assistantMessageCount++ : -1

              if (!isAssistant) {
                return (
                  <article key={message.id} className="flex justify-end gap-3">
                    <div className="flex max-w-[88%] flex-col items-end gap-2 sm:max-w-[72%]">
                      <span className="text-caption text-muted-foreground">你</span>
                      <div className="whitespace-pre-wrap break-words rounded-[var(--radius-lg)] rounded-tr-[0.35rem] bg-primary px-4 py-3 text-[14px] leading-7 text-primary-foreground shadow-sm sm:px-5">
                        {message.content}
                      </div>
                    </div>
                    <Avatar className="mt-6 h-8 w-8 shrink-0 border border-border-subtle bg-surface-elevated shadow-sm">
                      <AvatarFallback className="bg-transparent">
                        <User className="h-3.5 w-3.5 text-muted-foreground" />
                      </AvatarFallback>
                    </Avatar>
                  </article>
                )
              }

              return (
                <article
                  key={message.id}
                  className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3 sm:gap-4"
                >
                  <AssistantIdentity />
                  <div className="min-w-0 max-w-[46rem]">
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-xs font-semibold text-foreground">星仓 AI</span>
                      <span className="text-caption text-muted-foreground">AI 回复</span>
                    </div>
                    <div className="border-l-2 border-primary/20 bg-gradient-to-r from-primary/[0.045] to-transparent py-1 pl-4 pr-1 text-[15px] leading-7 text-foreground sm:pl-5 sm:text-[15.5px] sm:leading-8">
                      {message.isStreaming && !message.content ? (
                        <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                          正在整理信息…
                        </span>
                      ) : (
                        <span className="whitespace-pre-wrap break-words">{message.content}</span>
                      )}
                      {message.isStreaming && message.content && (
                        <span
                          className="ml-1 inline-block h-4 w-0.5 animate-pulse rounded-full bg-primary align-middle"
                          aria-hidden="true"
                        />
                      )}
                    </div>

                    {!message.isStreaming && onFeedback && (
                      <div className="mt-3">
                        {message.feedbackSentiment ? (
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>感谢你的反馈</span>
                            {message.feedbackSentiment === 'up' ? (
                              <ThumbsUp className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                            ) : (
                              <ThumbsDown className="h-3.5 w-3.5 text-danger" aria-hidden="true" />
                            )}
                          </div>
                        ) : (
                          <FeedbackWidget
                            messageId={message.id}
                            messageIndex={currentMessageIndex}
                            confidenceScore={message.metadata?.confidence_score}
                            onSubmit={onFeedback}
                            autoTrigger={
                              message.metadata?.confidence_score !== undefined &&
                              message.metadata.confidence_score < 0.6
                            }
                          />
                        )}
                      </div>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        </div>
      </ScrollArea>
    )
  }
)

ChatMessageList.displayName = 'ChatMessageList'
