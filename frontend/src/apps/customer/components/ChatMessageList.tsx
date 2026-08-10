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
                <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-lg shadow-indigo-200">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-500">
                    智能服务已就绪
                  </p>
                  <h2 className="mt-1 text-xl font-bold tracking-tight text-slate-950 sm:text-2xl">
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
                    className="group rounded-2xl border border-slate-200/80 bg-white/90 p-4 text-left shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-lg hover:shadow-indigo-100/70"
                  >
                    <div className="grid h-9 w-9 place-items-center rounded-xl bg-slate-100 text-slate-500 transition group-hover:bg-indigo-50 group-hover:text-indigo-600">
                      <Icon className="h-4 w-4" />
                    </div>
                    <p className="mt-4 text-sm font-semibold text-slate-900">{title}</p>
                    <p className="mt-1 text-xs text-slate-500">{description}</p>
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
                        ? 'border-slate-200 bg-white'
                        : 'border-indigo-100 bg-gradient-to-br from-indigo-500 to-violet-600 text-white'
                    }`}
                  >
                    <AvatarFallback className="bg-transparent">
                      {message.role === 'user' ? (
                        <User className="h-4 w-4 text-slate-500" />
                      ) : (
                        <Bot className="h-4 w-4" />
                      )}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex max-w-[86%] flex-col gap-2 sm:max-w-[78%]">
                    <div
                      className={`flex items-center gap-2 ${message.role === 'user' ? 'justify-end' : ''}`}
                    >
                      <span className="text-xs font-medium text-slate-500">
                        {message.role === 'user' ? '你' : '星仓AI'}
                      </span>
                      {isAssistant && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-emerald-600">
                          <ShieldCheck className="h-3 w-3" /> 安全响应
                        </span>
                      )}
                    </div>
                    <div
                      className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-[14px] leading-7 shadow-sm sm:px-5 ${
                        message.role === 'user'
                          ? 'rounded-tr-md bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-indigo-100'
                          : 'rounded-tl-md border border-slate-200/80 bg-white text-slate-700'
                      }`}
                    >
                      {message.content}
                      {message.isStreaming && (
                        <span className="ml-1 inline-block h-4 w-1.5 animate-pulse rounded-full bg-indigo-400" />
                      )}
                    </div>

                    {isAssistant && !message.isStreaming && message.id !== 'welcome' && (
                      <div className="flex items-center gap-1 text-[10px] text-slate-400">
                        <CheckCircle2 className="h-3 w-3 text-emerald-500" />
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
                                  ? 'bg-indigo-50 text-indigo-600'
                                  : 'text-slate-300'
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
                                  ? 'bg-red-50 text-red-600'
                                  : 'text-slate-300'
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
                <Avatar className="h-9 w-9 border border-indigo-100 bg-gradient-to-br from-indigo-500 to-violet-600 text-white">
                  <AvatarFallback className="bg-transparent">
                    <Bot className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
                <div className="flex items-center gap-2 rounded-2xl rounded-tl-md border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />
                  <span className="text-sm text-slate-500">正在理解并连接相关服务...</span>
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
