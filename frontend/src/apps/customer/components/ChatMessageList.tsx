import { forwardRef } from 'react'
import {
  Bot,
  CheckCircle2,
  Loader2,
  PackageSearch,
  ReceiptText,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Truck,
  User,
} from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
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
    title: '查订单',
    description: '快速了解订单状态',
    icon: PackageSearch,
    prompt: '查询我的最近订单',
  },
  {
    title: '看物流',
    description: '获取最新物流进度',
    icon: Truck,
    prompt: '我的订单物流到哪里了？',
  },
  {
    title: '退换货',
    description: '了解政策并发起申请',
    icon: ReceiptText,
    prompt: '我想了解退换货政策',
  },
]

/** Render the active customer conversation and its service states. */
export const ChatMessageList = forwardRef<HTMLDivElement, ChatMessageListProps>(
  ({ messages, isLoading, onFeedback, onQuickTask }, ref) => {
    let assistantMessageCount = 0

    return (
      <ScrollArea className="relative z-10 flex-1" ref={ref}>
        <div className="mx-auto w-full max-w-4xl px-4 pb-10 pt-8 sm:px-8 sm:pt-12">
          {messages.length === 1 && (
            <section className="mb-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
              <div className="mb-5 flex items-center gap-3">
                <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[image:var(--gradient-primary)] text-primary-foreground shadow-md">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                    智能服务已就绪
                  </p>
                  <h2 className="mt-1 text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
                    今天想先处理什么？
                  </h2>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {WELCOME_TASKS.map(({ title, description, icon: Icon, prompt }) => (
                  <button
                    key={title}
                    type="button"
                    onClick={() => onQuickTask?.(prompt)}
                    className="group rounded-2xl border border-border-subtle bg-surface/88 p-4 text-left shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:bg-surface-elevated hover:shadow-md"
                  >
                    <div className="grid h-9 w-9 place-items-center rounded-xl bg-muted text-muted-foreground transition group-hover:bg-primary/10 group-hover:text-primary">
                      <Icon className="h-4 w-4" />
                    </div>
                    <p className="mt-4 text-sm font-semibold text-foreground">{title}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{description}</p>
                  </button>
                ))}
              </div>
            </section>
          )}

          <div className="space-y-7">
            {messages.map((message) => {
              const isAssistant = message.role === 'assistant'
              const currentMessageIndex = isAssistant ? assistantMessageCount++ : -1

              return (
                <article
                  key={message.id}
                  className={`flex gap-3 sm:gap-4 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  <Avatar
                    className={`h-9 w-9 shrink-0 border shadow-sm ${
                      message.role === 'user'
                        ? 'border-border-subtle bg-surface-elevated'
                        : 'border-primary/15 bg-[image:var(--gradient-primary)] text-primary-foreground'
                    }`}
                  >
                    <AvatarFallback className="bg-transparent">
                      {message.role === 'user' ? (
                        <User className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Bot className="h-4 w-4" />
                      )}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex max-w-[86%] flex-col gap-2 sm:max-w-[78%]">
                    <div
                      className={`flex items-center gap-2 ${message.role === 'user' ? 'justify-end' : ''}`}
                    >
                      <span className="text-xs font-medium text-muted-foreground">
                        {message.role === 'user' ? '你' : '星仓 AI'}
                      </span>
                      {isAssistant && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-success">
                          <ShieldCheck className="h-3 w-3" /> 安全响应
                        </span>
                      )}
                    </div>
                    <div
                      className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-[14px] leading-7 shadow-sm sm:px-5 ${
                        message.role === 'user'
                          ? 'rounded-tr-md bg-[image:var(--gradient-primary)] text-primary-foreground'
                          : 'rounded-tl-md border border-border-subtle bg-surface-elevated text-foreground'
                      }`}
                    >
                      {message.content}
                      {message.isStreaming && (
                        <span className="ml-1 inline-block h-4 w-1.5 animate-pulse rounded-full bg-primary" />
                      )}
                    </div>

                    {isAssistant && !message.isStreaming && message.id !== 'welcome' && (
                      <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                        <CheckCircle2 className="h-3 w-3 text-success" />
                        已完成本次智能分析
                      </div>
                    )}

                    {isAssistant && !message.isStreaming && onFeedback && (
                      <div className="flex flex-col gap-1">
                        {message.feedbackSentiment ? (
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className={`h-7 w-7 ${
                                message.feedbackSentiment === 'up'
                                  ? 'bg-primary/10 text-primary'
                                  : 'text-muted-foreground'
                              }`}
                              disabled
                              aria-label="已点赞"
                            >
                              <ThumbsUp className="h-3 w-3" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className={`h-7 w-7 ${
                                message.feedbackSentiment === 'down'
                                  ? 'bg-danger/10 text-danger'
                                  : 'text-muted-foreground'
                              }`}
                              disabled
                              aria-label="已点踩"
                            >
                              <ThumbsDown className="h-3 w-3" />
                            </Button>
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

            {isLoading && messages[messages.length - 1]?.role === 'user' && (
              <div className="flex gap-4">
                <Avatar className="h-9 w-9 border border-primary/15 bg-[image:var(--gradient-primary)] text-primary-foreground">
                  <AvatarFallback className="bg-transparent">
                    <Bot className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
                <div className="flex items-center gap-2 rounded-2xl rounded-tl-md border border-border-subtle bg-surface-elevated px-4 py-3 shadow-sm">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  <span className="text-sm text-muted-foreground">正在理解并连接相关服务...</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </ScrollArea>
    )
  }
)

ChatMessageList.displayName = 'ChatMessageList'
