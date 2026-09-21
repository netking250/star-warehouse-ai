import { type FC, useEffect, useRef, useState } from 'react'
import {
  ArrowRight,
  BellRing,
  Check,
  ChevronRight,
  Clock3,
  LoaderCircle,
  LogOut,
  Menu,
  PackageSearch,
  Plus,
  ReceiptText,
  ShieldCheck,
  Sparkles,
  Truck,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { BrandMark, StarWarehouseLogo } from '@/components/brand/StarWarehouseLogo'
import { AppBackground } from '@/components/shell/AppShell'
import { ThemeToggle } from '@/components/theme/ThemeToggle'
import { Input } from '@/components/ui/input'
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
    user,
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
  const displayName = user?.full_name?.trim() || user?.username || '当前账户'
  const accountLabel =
    user?.username && user.username !== displayName ? user.username : '已登录账户'
  const accountInitial = Array.from(displayName)[0]?.toUpperCase() || '星'

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
  const { isConnected } = useWebSocket({
    url: wsUrl,
    enabled: isAuthenticated,
    onMessage: handleWsMessage,
  })

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages])

  useEffect(() => {
    if (!sidebarOpen) return
    const closeOnEscape = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setSidebarOpen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [sidebarOpen])

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

  if (!isInitialized) {
    return (
      <main className="relative grid min-h-[100dvh] place-items-center overflow-hidden bg-background text-foreground">
        <AppBackground />
        <div className="relative z-10 flex flex-col items-center" role="status" aria-live="polite">
          <div className="brand-mark-shell grid h-16 w-16 place-items-center rounded-[var(--radius-lg)]">
            <BrandMark className="h-12 w-12" />
          </div>
          <p className="mt-5 text-sm font-medium text-foreground">正在恢复会话</p>
          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
            <LoaderCircle className="h-3.5 w-3.5 animate-spin text-primary" aria-hidden="true" />
            正在确认登录状态…
          </div>
        </div>
      </main>
    )
  }

  if (!isAuthenticated) {
    return (
      <main className="relative min-h-[100dvh] overflow-hidden bg-background text-foreground">
        <AppBackground />
        <div className="absolute right-4 top-4 z-20 sm:right-6 sm:top-6">
          <ThemeToggle />
        </div>
        <div className="relative mx-auto grid min-h-[100dvh] max-w-[78rem] items-center gap-10 px-5 py-20 sm:px-8 lg:grid-cols-[1.08fr_0.92fr] lg:gap-20 lg:px-12">
          <section className="hidden lg:block" aria-labelledby="customer-login-positioning">
            <StarWarehouseLogo />
            <p className="mt-20 text-caption uppercase tracking-[0.24em] text-primary">
              Enterprise AI Service Platform
            </p>
            <h1
              id="customer-login-positioning"
              className="mt-5 max-w-2xl text-[2.9rem] font-semibold leading-[1.08] tracking-[-0.05em] text-foreground 2xl:text-[3.4rem]"
            >
              企业智能服务，
              <span className="brand-gradient-text block">从理解开始。</span>
            </h1>
            <p className="mt-6 max-w-lg text-[15px] leading-8 text-muted-foreground">
              星仓 AI 连接企业知识与业务服务，帮助客户清晰处理订单、物流、售后政策与商品咨询。
            </p>
            <ul className="mt-10 space-y-4" aria-label="平台能力">
              {['连接企业知识与业务服务', '智能理解客户需求', '关键操作保持人工审批边界'].map(
                (item) => (
                  <li key={item} className="flex items-center gap-3 text-sm text-foreground">
                    <span className="grid h-6 w-6 place-items-center rounded-full bg-primary/10 text-primary">
                      <Check className="h-3.5 w-3.5" aria-hidden="true" />
                    </span>
                    {item}
                  </li>
                )
              )}
            </ul>
          </section>

          <Card className="glass-panel mx-auto w-full max-w-[28rem] overflow-hidden rounded-[var(--radius-xl)] border-border-subtle bg-surface-elevated/88 shadow-lg">
            <div
              className="h-px bg-[image:var(--gradient-primary)] opacity-65"
              aria-hidden="true"
            />
            <CardContent className="p-6 sm:p-9">
              <StarWarehouseLogo className="mb-10 lg:hidden" />
              <div className="mb-8 flex items-start gap-4">
                <div className="brand-mark-shell grid h-11 w-11 shrink-0 place-items-center rounded-[var(--radius-md)]">
                  <BrandMark className="h-8 w-8" />
                </div>
                <div>
                  <h2 className="text-2xl font-semibold tracking-[-0.035em] text-foreground">
                    登录客户服务
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    使用已授权的账户继续访问星仓 AI。
                  </p>
                </div>
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
                    placeholder="请输入账号"
                    className="h-12 rounded-[var(--radius-md)] bg-surface/80 px-4"
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
                    placeholder="请输入密码"
                    className="h-12 rounded-[var(--radius-md)] bg-surface/80 px-4"
                    autoComplete="current-password"
                    required
                  />
                </div>
                {loginError && (
                  <p
                    className="rounded-[var(--radius-md)] border border-danger/15 bg-danger/8 px-3 py-2.5 text-sm text-danger"
                    role="alert"
                  >
                    {loginError}
                  </p>
                )}
                <Button
                  type="submit"
                  className="h-12 w-full rounded-[var(--radius-md)] bg-[image:var(--gradient-primary)] shadow-md"
                  disabled={isLoginLoading}
                >
                  {isLoginLoading ? '正在登录…' : '进入星仓 AI'}
                  {!isLoginLoading && <ArrowRight className="h-4 w-4" />}
                </Button>
              </form>
              <p className="mt-7 flex items-center justify-center gap-2 text-center text-xs leading-5 text-muted-foreground">
                <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
                会话由受保护的服务端会话管理
              </p>
            </CardContent>
          </Card>
        </div>
      </main>
    )
  }

  const renderSidebarContent = (): React.ReactElement => (
    <>
      <div className="flex h-[72px] items-center justify-between border-b border-border-subtle px-5">
        <StarWarehouseLogo />
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-5">
        <Button
          onClick={handleNewConversation}
          className="h-11 w-full justify-start rounded-[var(--radius-md)] border border-primary/15 bg-primary/10 text-primary shadow-none hover:bg-primary/15"
          data-testid="new-conversation-button"
        >
          <Plus className="h-4 w-4" />
          开启新对话
        </Button>

        <nav className="mt-8" aria-label="常用服务">
          <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            常用服务
          </p>
          <div className="mt-3 space-y-1">
            {QUICK_TASKS.map(({ label, prompt, icon: Icon }) => (
              <button
                type="button"
                key={label}
                onClick={() => handleQuickTask(prompt)}
                disabled={isLoading}
                className="group flex min-h-10 w-full items-center gap-3 rounded-[var(--radius-md)] px-3 py-2.5 text-left text-sm text-muted-foreground transition-[background-color,color] duration-150 hover:bg-primary/8 hover:text-foreground disabled:opacity-50"
              >
                <Icon className="h-4 w-4 text-muted-foreground transition group-hover:text-primary" />
                <span className="flex-1">{label}</span>
                <ChevronRight className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" />
              </button>
            ))}
          </div>
        </nav>

        <div className="mt-8 rounded-[var(--radius-lg)] border border-border-subtle bg-surface/72 p-4">
          <div className="flex items-center gap-2 text-xs font-medium text-foreground">
            <BellRing className="h-4 w-4" />
            服务连接
          </div>
          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {isConnected ? '智能服务已连接' : '正在建立服务连接'}
            </span>
            <span
              className={`h-2 w-2 rounded-full ${isConnected ? 'bg-success' : 'bg-muted-foreground/45'}`}
              aria-hidden="true"
            />
          </div>
        </div>
      </div>

      <div className="border-t border-border-subtle p-4">
        <div className="flex items-center gap-3 rounded-[var(--radius-md)] px-2 py-2">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-[var(--radius-md)] bg-primary/10 text-sm font-semibold text-primary">
            {accountInitial}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{displayName}</p>
            <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{accountLabel}</p>
          </div>
        </div>
      </div>
    </>
  )

  return (
    <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
      <main className="relative flex h-[100dvh] overflow-hidden bg-background text-foreground">
        <AppBackground />

        <aside
          aria-label="客户服务导航"
          className="hidden w-[18rem] shrink-0 flex-col border-r border-border-subtle bg-surface-elevated/94 text-foreground lg:flex"
        >
          {renderSidebarContent()}
        </aside>

        <SheetContent
          aria-describedby={undefined}
          closeLabel="关闭菜单"
          className="glass-panel left-0 right-auto flex w-[min(19rem,88vw)] flex-col gap-0 border-l-0 border-r border-border-subtle bg-surface-elevated/94 p-0 text-foreground shadow-lg data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left sm:max-w-[19rem] lg:hidden"
        >
          <SheetTitle className="sr-only">客户服务导航</SheetTitle>
          {renderSidebarContent()}
        </SheetContent>

        <section className="relative z-10 flex min-w-0 flex-1 flex-col">
          <header className="glass-panel z-20 flex h-[72px] shrink-0 items-center justify-between border-b px-3 sm:px-6">
            <div className="flex items-center gap-3">
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" aria-label="打开菜单">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <div>
                <h1 className="text-sm font-semibold tracking-[-0.015em] sm:text-base">
                  星仓 AI 服务助手
                </h1>
                <p className="mt-1 hidden text-xs text-muted-foreground sm:block">
                  订单、物流、售后与企业知识
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <ThemeToggle />
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground"
                data-testid="logout-button"
                aria-label="退出登录"
                title="退出登录"
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

        <div
          className="fixed left-3 right-3 top-3 z-50 flex flex-col gap-2 sm:left-auto sm:right-6 sm:top-20 sm:w-[22rem]"
          aria-live="polite"
          aria-label="服务通知"
        >
          {toasts.map((toast) => (
            <div
              key={toast.id}
              role="status"
              className="glass-panel page-enter w-full rounded-[var(--radius-lg)] border px-4 py-3 shadow-lg"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 grid h-8 w-8 place-items-center rounded-xl bg-primary/10 text-primary">
                  <Clock3 className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-foreground">{toast.title}</p>
                  <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{toast.message}</p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="-mr-2 -mt-1 h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
                  onClick={() => setToasts((prev) => prev.filter((item) => item.id !== toast.id))}
                  aria-label="关闭通知"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </main>
    </Sheet>
  )
}

export default App
