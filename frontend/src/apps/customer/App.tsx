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
  const { isAuthenticated, login, logout, isLoading: isLoginLoading, error: loginError } = useAuth()
  const { messages, isLoading, sendMessage, submitFeedback, resetMessages } = useChat()
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

  if (!isAuthenticated) {
    return (
      <main className="relative min-h-screen overflow-hidden bg-slate-950">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(99,102,241,0.35),transparent_34%),radial-gradient(circle_at_80%_75%,rgba(34,211,238,0.2),transparent_30%)]" />
        <div className="star-grid absolute inset-0 opacity-20" />
        <div className="relative mx-auto grid min-h-screen max-w-7xl items-center gap-12 px-6 py-10 lg:grid-cols-[1.08fr_0.92fr] lg:px-12">
          <section className="hidden text-white lg:block">
            <StarWarehouseLogo inverse />
            <p className="mt-20 text-xs font-semibold uppercase tracking-[0.3em] text-cyan-300">
              Enterprise AI Service Platform
            </p>
            <h1 className="mt-5 max-w-xl text-5xl font-semibold leading-[1.12] tracking-tight">
              让每一次服务，
              <span className="bg-gradient-to-r from-indigo-300 to-cyan-200 bg-clip-text text-transparent">
                更快抵达答案
              </span>
            </h1>
            <p className="mt-6 max-w-lg text-base leading-8 text-slate-300">
              星仓AI连接订单、物流、商品与企业知识，为客户提供可信、专业、有温度的智能服务体验。
            </p>
            <div className="mt-10 grid max-w-xl grid-cols-3 gap-3">
              {[
                ['7×24', '全天候响应'],
                ['秒级', '意图理解'],
                ['全链路', '安全可追溯'],
              ].map(([value, label]) => (
                <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.06] p-4">
                  <p className="text-xl font-semibold text-white">{value}</p>
                  <p className="mt-1 text-xs text-slate-400">{label}</p>
                </div>
              ))}
            </div>
          </section>

          <Card className="mx-auto w-full max-w-md border-white/60 bg-white/95 shadow-2xl shadow-indigo-950/30 backdrop-blur-xl">
            <CardContent className="p-7 sm:p-9">
              <StarWarehouseLogo className="mb-10 lg:hidden" />
              <div className="mb-8">
                <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                  <MessageSquareText className="h-5 w-5" />
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-950">欢迎回来</h2>
                <p className="mt-2 text-sm text-slate-500">登录后继续您的专属智能服务</p>
              </div>
              <form onSubmit={(event) => void handleLogin(event)} className="space-y-5">
                <div className="space-y-2">
                  <label htmlFor="customer-username" className="text-sm font-medium text-slate-700">
                    账号
                  </label>
                  <Input
                    id="customer-username"
                    value={loginForm.username}
                    onChange={(event) =>
                      setLoginForm({ ...loginForm, username: event.target.value })
                    }
                    placeholder="请输入您的账号"
                    className="h-12 bg-slate-50/80"
                    autoComplete="username"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="customer-password" className="text-sm font-medium text-slate-700">
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
                    className="h-12 bg-slate-50/80"
                    autoComplete="current-password"
                    required
                  />
                </div>
                {loginError && (
                  <p className="rounded-xl bg-red-50 px-3 py-2.5 text-sm text-red-600" role="alert">
                    {loginError}
                  </p>
                )}
                <Button
                  type="submit"
                  className="h-12 w-full rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 shadow-lg shadow-indigo-200 hover:from-indigo-500 hover:to-violet-500"
                  disabled={isLoginLoading}
                >
                  {isLoginLoading ? '安全登录中...' : '进入星仓AI'}
                  {!isLoginLoading && <ArrowRight className="h-4 w-4" />}
                </Button>
              </form>
              <div className="mt-7 flex items-center justify-center gap-2 text-xs text-slate-400">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                企业级加密传输 · 会话安全受保护
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    )
  }

  return (
    <main className="flex h-screen overflow-hidden bg-[#f5f7fb] text-slate-900">
      {sidebarOpen && (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-slate-950/35 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="关闭菜单"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[278px] flex-col border-r border-white/10 bg-slate-950 text-white transition-transform duration-300 lg:static lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-[76px] items-center justify-between border-b border-white/10 px-5">
          <StarWarehouseLogo inverse />
          <Button
            variant="ghost"
            size="icon"
            className="text-slate-300 hover:bg-white/10 hover:text-white lg:hidden"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-5">
          <Button
            onClick={handleNewConversation}
            className="h-11 w-full justify-start rounded-xl border border-white/10 bg-white/10 text-white shadow-none hover:bg-white/15"
          >
            <Plus className="h-4 w-4" />
            开启新对话
          </Button>

          <div className="mt-7">
            <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              常用服务
            </p>
            <div className="mt-3 space-y-1.5">
              {QUICK_TASKS.map(({ label, prompt, icon: Icon }) => (
                <button
                  type="button"
                  key={label}
                  onClick={() => handleQuickTask(prompt)}
                  disabled={isLoading}
                  className="group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-slate-300 transition hover:bg-white/[0.08] hover:text-white disabled:opacity-50"
                >
                  <Icon className="h-4 w-4 text-slate-500 transition group-hover:text-cyan-300" />
                  <span className="flex-1">{label}</span>
                  <ChevronRight className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" />
                </button>
              ))}
            </div>
          </div>

          <div className="mt-8 rounded-2xl border border-indigo-400/20 bg-gradient-to-br from-indigo-500/15 to-cyan-400/5 p-4">
            <div className="flex items-center gap-2 text-xs font-medium text-indigo-200">
              <BellRing className="h-4 w-4 text-cyan-300" />
              服务状态
            </div>
            <div className="mt-3 flex items-center justify-between text-sm">
              <span className="text-slate-300">AI 服务运行正常</span>
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.9)]" />
            </div>
          </div>
        </div>

        <div className="border-t border-white/10 p-4">
          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-xl p-2 text-left hover:bg-white/[0.06]"
          >
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 text-sm font-semibold">
              星
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">尊享用户</p>
              <p className="mt-0.5 text-[11px] text-slate-500">专属智能服务已开启</p>
            </div>
          </button>
        </div>
      </aside>

      <section className="relative flex min-w-0 flex-1 flex-col">
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
                <h1 className="text-sm font-semibold sm:text-base">星仓AI 服务助手</h1>
                <span className="hidden rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-600 sm:inline-flex">
                  在线
                </span>
              </div>
              <p className="mt-1 hidden text-xs text-slate-400 sm:block">
                智能理解需求，为您连接完整服务链路
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="text-slate-500" aria-label="帮助中心">
              <CircleHelp className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-slate-500"
              onClick={() => void logout()}
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">退出</span>
            </Button>
          </div>
        </header>

        <div className="star-grid absolute inset-x-0 top-[76px] h-64 opacity-40" />
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
          isLoading={isLoading}
          placeholder="告诉星仓AI，您需要什么帮助..."
        />
      </section>

      <div className="fixed right-4 top-4 z-50 flex flex-col gap-2 sm:right-6 sm:top-6">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="glass-panel min-w-[17rem] max-w-sm rounded-2xl border border-white px-4 py-3 shadow-xl shadow-slate-900/10"
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 grid h-8 w-8 place-items-center rounded-xl bg-indigo-50 text-indigo-600">
                <Clock3 className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-900">{toast.title}</p>
                <p className="mt-0.5 text-xs leading-5 text-slate-500">{toast.message}</p>
              </div>
              <button
                type="button"
                className="text-slate-400 hover:text-slate-600"
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
