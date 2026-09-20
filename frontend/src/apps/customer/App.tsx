import { type FC, useEffect, useRef, useState } from 'react'
import {
  ArrowRight,
  BellRing,
  ChevronRight,
  CircleHelp,
  Clock3,
  LogOut,
  Menu,
  MessageSquareText,
  PackageSearch,
  Plus,
  ReceiptText,
  ShieldCheck,
  Sparkles,
  Truck,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { StarWarehouseLogo } from '@/components/brand/StarWarehouseLogo'
import { AppBackground } from '@/components/shell/AppShell'
import { ThemeToggle } from '@/components/theme/ThemeToggle'
import { useAuth } from '@/hooks/useAuth'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { WSMessage } from '@/types'
import { ChatInput } from './components/ChatInput'
import { ChatMessageList } from './components/ChatMessageList'
import { useChat } from './hooks/useChat'

interface StatusToast {
  id: string
  title: string
  message: string
}

const QUICK_TASKS = [
  { label: '查询我的订单', prompt: '帮我查询一下最近的订单状态', icon: PackageSearch },
  { label: '物流到哪了', prompt: '帮我查询一下订单的物流进度', icon: Truck },
  { label: '退换货政策', prompt: '请介绍一下退换货政策和办理条件', icon: ReceiptText },
  { label: '商品选购建议', prompt: '我想选购商品，请根据我的需求给一些建议', icon: Sparkles },
]

const App: FC = () => {
  const {
    isAuthenticated,
    isInitialized,
    login,
    logout,
    isLoading: isLoginLoading,
    error: loginError,
  } = useAuth()
  const { messages, isLoading, sendMessage, cancelGeneration, submitFeedback, resetMessages } =
    useChat()
  const [input, setInput] = useState('')
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const [toasts, setToasts] = useState<StatusToast[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const threadId = useRef(`thread_${Date.now()}`)

  const addToast = (title: string, message: string): void => {
    const id = `${Date.now()}_${Math.random()}`
    setToasts((prev) => [...prev, { id, title, message }])
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id))
    }, 5000)
  }

  const handleWsMessage = (message: WSMessage): void => {
    if (message.type !== 'status_change') return
    const payload = message.payload as
      | { title?: string; message?: string; status?: string }
      | undefined
    addToast(
      payload?.title || '服务进度更新',
      payload?.message || payload?.status || '您的请求状态已更新'
    )
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/${threadId.current}`
  useWebSocket({ url: wsUrl, enabled: isAuthenticated, onMessage: handleWsMessage })

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages])

  const handleLogin = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault()
    try {
      await login(loginForm)
    } catch {
      // Authentication errors are displayed from the shared auth hook.
    }
  }

  const handleSend = (): void => {
    if (!input.trim() || isLoading) return
    void sendMessage(input, threadId.current)
    setInput('')
  }

  const handleQuickTask = (prompt: string): void => {
    if (isLoading) return
    void sendMessage(prompt, threadId.current)
    setSidebarOpen(false)
  }

  const handleNewConversation = (): void => {
    threadId.current = `thread_${Date.now()}`
    resetMessages()
    setInput('')
    setSidebarOpen(false)
  }

  const handleFeedback = (
    messageId: string,
    sentiment: 'up' | 'down',
    messageIndex: number,
    category?: string,
    comment?: string
  ): void => {
    void submitFeedback(messageId, sentiment, threadId.current, messageIndex, category, comment)
  }

  if (!isInitialized) return <main className="min-h-screen bg-background" />

  if (!isAuthenticated) {
    return (
      <main className="relative min-h-screen overflow-hidden bg-background text-foreground">
        <AppBackground />
        <div className="absolute right-5 top-5 z-20">
          <ThemeToggle />
        </div>
        <div className="relative mx-auto grid min-h-screen max-w-7xl items-center gap-12 px-6 py-10 lg:grid-cols-[1.08fr_0.92fr] lg:px-12">
          <section className="hidden lg:block">
            <StarWarehouseLogo />
            <p className="mt-20 text-xs font-semibold uppercase tracking-[0.3em] text-primary">
              Enterprise AI Service Platform
            </p>
            <h1 className="mt-5 max-w-2xl text-[2.75rem] font-semibold leading-[1.12] tracking-tight text-foreground 2xl:text-5xl">
              让每一次服务，
              <span className="brand-gradient-text">更快抵达答案</span>
            </h1>
            <p className="mt-6 max-w-lg text-base leading-8 text-muted-foreground">
              星仓 AI 连接订单、物流、商品与企业知识，为客户提供可信、专业、有温度的智能服务体验。
            </p>
            <div className="mt-10 grid max-w-xl grid-cols-3 gap-3">
              {[
                ['7×24', '全天候响应'],
                ['秒级', '意图理解'],
                ['全链路', '安全可追溯'],
              ].map(([value, label]) => (
                <div key={label} className="glass-panel rounded-2xl border p-4">
                  <p className="numeric text-xl font-semibold text-foreground">{value}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{label}</p>
                </div>
              ))}
            </div>
          </section>

          <Card className="mx-auto w-full max-w-md border-border-subtle bg-surface-elevated/90 shadow-lg backdrop-blur-xl">
            <CardContent className="p-7 sm:p-9">
              <StarWarehouseLogo className="mb-10 lg:hidden" />
              <div className="mb-8">
                <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <MessageSquareText className="h-5 w-5" />
                </div>
                <h2 className="text-2xl font-semibold tracking-tight text-foreground">欢迎回来</h2>
                <p className="mt-2 text-sm text-muted-foreground">登录后继续您的专属智能服务</p>
              </div>
              <form onSubmit={(event) => void handleLogin(event)} className="space-y-5">
                <div className="space-y-2">
                  <label
                    htmlFor="customer-username"
                    className="text-sm font-medium text-foreground"
                  >
                    账号
                  </label>
                  <Input
                    id="customer-username"
                    value={loginForm.username}
                    onChange={(event) =>
                      setLoginForm({ ...loginForm, username: event.target.value })
                    }
                    placeholder="请输入您的账号"
                    className="h-12 bg-surface/70"
                    autoComplete="username"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label
                    htmlFor="customer-password"
                    className="text-sm font-medium text-foreground"
                  >
                    密码
                  </label>
                  <Input
                    id="customer-password"
                    type="password"
                    value={loginForm.password}
                    onChange={(event) =>
                      setLoginForm({ ...loginForm, password: event.target.value })
                    }
                    placeholder="请输入您的密码"
                    className="h-12 bg-surface/70"
                    autoComplete="current-password"
                    required
                  />
                </div>
                {loginError && (
                  <p
                    className="rounded-xl bg-danger/10 px-3 py-2.5 text-sm text-danger"
                    role="alert"
                  >
                    {loginError}
                  </p>
                )}
                <Button
                  type="submit"
                  className="h-12 w-full rounded-xl bg-[image:var(--gradient-primary)] shadow-md"
                  disabled={isLoginLoading}
                >
                  {isLoginLoading ? '安全登录中...' : '进入星仓 AI'}
                  {!isLoginLoading && <ArrowRight className="h-4 w-4" />}
                </Button>
              </form>
              <div className="mt-7 flex items-center justify-center gap-2 text-xs text-muted-foreground">
                <ShieldCheck className="h-3.5 w-3.5 text-success" />
                企业级加密传输 · 会话安全受保护
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    )
  }

  return (
    <main className="relative flex h-screen overflow-hidden bg-background text-foreground">
      <AppBackground />
      {sidebarOpen && (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-foreground/25 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="关闭菜单"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[278px] flex-col border-r border-border-subtle bg-surface-elevated/95 text-foreground shadow-md backdrop-blur-xl transition-transform duration-300 lg:static lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-[76px] items-center justify-between border-b border-border-subtle px-5">
          <StarWarehouseLogo />
          <Button
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-5">
          <Button
            onClick={handleNewConversation}
            className="h-11 w-full justify-start rounded-xl border border-primary/15 bg-primary/10 text-primary shadow-none hover:bg-primary/15"
          >
            <Plus className="h-4 w-4" />
            开启新对话
          </Button>

          <div className="mt-7">
            <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              常用服务
            </p>
            <div className="mt-3 space-y-1.5">
              {QUICK_TASKS.map(({ label, prompt, icon: Icon }) => (
                <button
                  type="button"
                  key={label}
                  onClick={() => handleQuickTask(prompt)}
                  disabled={isLoading}
                  className="group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-muted-foreground transition hover:bg-primary/8 hover:text-foreground disabled:opacity-50"
                >
                  <Icon className="h-4 w-4 text-muted-foreground transition group-hover:text-primary" />
                  <span className="flex-1">{label}</span>
                  <ChevronRight className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" />
                </button>
              ))}
            </div>
          </div>

          <div className="mt-8 rounded-2xl border border-primary/15 bg-primary/8 p-4">
            <div className="flex items-center gap-2 text-xs font-medium text-primary">
              <BellRing className="h-4 w-4" />
              服务状态
            </div>
            <div className="mt-3 flex items-center justify-between text-sm">
              <span className="text-muted-foreground">AI 服务运行正常</span>
              <span className="h-2 w-2 rounded-full bg-success shadow-glow" />
            </div>
          </div>
        </div>

        <div className="border-t border-border-subtle p-4">
          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-xl p-2 text-left hover:bg-muted"
          >
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-[image:var(--gradient-primary)] text-sm font-semibold text-primary-foreground">
              星
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">尊享用户</p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">专属智能服务已开启</p>
            </div>
          </button>
        </div>
      </aside>

      <section className="relative z-10 flex min-w-0 flex-1 flex-col">
        <header className="glass-panel z-20 flex h-[76px] shrink-0 items-center justify-between border-b px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setSidebarOpen(true)}
              aria-label="打开菜单"
            >
              <Menu className="h-5 w-5" />
            </Button>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-semibold sm:text-base">星仓 AI 服务助手</h1>
                <span className="hidden rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success sm:inline-flex">
                  在线
                </span>
              </div>
              <p className="mt-1 hidden text-xs text-muted-foreground sm:block">
                智能理解需求，为您连接完整服务链路
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground"
              aria-label="帮助中心"
            >
              <CircleHelp className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              data-testid="logout-button"
              onClick={() => void logout()}
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">退出</span>
            </Button>
          </div>
        </header>

        <ChatMessageList
          messages={messages}
          isLoading={isLoading}
          ref={scrollRef}
          onFeedback={handleFeedback}
          onQuickTask={handleQuickTask}
        />
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onCancel={() => void cancelGeneration()}
          isLoading={isLoading}
          placeholder="告诉星仓 AI，您需要什么帮助..."
        />
      </section>

      <div className="fixed right-4 top-4 z-50 flex flex-col gap-2 sm:right-6 sm:top-6">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="glass-panel min-w-[17rem] max-w-sm rounded-2xl border px-4 py-3 shadow-lg"
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 grid h-8 w-8 place-items-center rounded-xl bg-primary/10 text-primary">
                <Clock3 className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-foreground">{toast.title}</p>
                <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{toast.message}</p>
              </div>
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground"
                onClick={() => setToasts((prev) => prev.filter((item) => item.id !== toast.id))}
                aria-label="关闭通知"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </main>
  )
}

export default App
