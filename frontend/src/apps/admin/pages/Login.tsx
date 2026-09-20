import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Loader2, LockKeyhole, ShieldCheck } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { StarWarehouseLogo } from '@/components/brand/StarWarehouseLogo'
import { AppBackground } from '@/components/shell/AppShell'
import { ThemeToggle } from '@/components/theme/ThemeToggle'
import { useAuth } from '@/hooks/useAuth'
import { useAuthStore } from '@/stores/auth'

/** Render the secure Star Warehouse AI operations login. */
export function Login(): React.ReactElement {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { login, isLoading, error } = useAuth()
  const { isAuthenticated, user } = useAuthStore()

  if (isAuthenticated && user?.role === 'ADMIN') {
    return <Navigate to="/" replace />
  }

  const handleSubmit = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault()
    await login({ username, password })
  }

  return (
    <main className="relative grid min-h-screen overflow-hidden bg-background lg:grid-cols-[1fr_520px]">
      <AppBackground />
      <ThemeToggle className="glass-panel fixed right-5 top-5 z-30 border" />
      <section className="relative z-10 hidden overflow-hidden bg-foreground p-14 text-background dark:bg-surface dark:text-foreground lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[var(--gradient-ambient)] opacity-80" />
        <div className="ambient-grid absolute inset-0 opacity-20" />
        <StarWarehouseLogo inverse className="relative" />
        <div className="relative my-auto max-w-xl">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-info">
            AI Customer Service OS
          </p>
          <h1 className="mt-5 text-5xl font-semibold leading-tight tracking-tight">
            看见每一次服务，
            <br />
            掌控每一个关键决策
          </h1>
          <p className="mt-6 max-w-lg text-base leading-8 text-background/70 dark:text-foreground/70">
            从知识治理、Agent 配置到风险审核与质量评估，星仓 AI
            为运营团队提供统一、可信、可追溯的工作空间。
          </p>
          <div className="mt-10 space-y-4">
            {['全链路服务质量观测', '高风险操作人工审核', '企业知识与策略统一治理'].map((item) => (
              <div
                key={item}
                className="flex items-center gap-3 text-sm text-background/72 dark:text-foreground/72"
              >
                <CheckCircle2 className="h-4 w-4 text-info" />
                {item}
              </div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-background/35 dark:text-foreground/35">
          Star Warehouse AI · Enterprise Edition
        </p>
      </section>

      <section className="relative z-10 flex items-center justify-center px-5 py-10 lg:px-12">
        <Card className="glass-panel relative w-full max-w-md border-border-subtle bg-surface/84 shadow-lg">
          <CardContent className="p-7 sm:p-10">
            <StarWarehouseLogo className="mb-10 lg:hidden" />
            <div className="mb-8">
              <div className="mb-5 grid h-12 w-12 place-items-center rounded-lg bg-primary/10 text-primary">
                <LockKeyhole className="h-5 w-5" />
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                登录运营中心
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">仅授权的企业管理员可以访问</p>
            </div>
            <form onSubmit={(event) => void handleSubmit(event)} className="space-y-5">
              {error && (
                <Alert variant="destructive" className="rounded-xl">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <div className="space-y-2">
                <label htmlFor="admin-username" className="text-sm font-medium text-foreground/85">
                  管理员账号
                </label>
                <Input
                  id="admin-username"
                  type="text"
                  placeholder="请输入管理员账号"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  className="h-12 bg-surface-elevated/70"
                  autoComplete="username"
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="admin-password" className="text-sm font-medium text-foreground/85">
                  登录密码
                </label>
                <Input
                  id="admin-password"
                  type="password"
                  placeholder="请输入登录密码"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="h-12 bg-surface-elevated/70"
                  autoComplete="current-password"
                  required
                />
              </div>
              <Button
                type="submit"
                className="h-12 w-full rounded-md bg-[var(--gradient-primary)] shadow-glow"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> 安全验证中...
                  </>
                ) : (
                  <>
                    进入运营中心 <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </form>
            <div className="mt-8 flex items-center justify-center gap-2 border-t border-border-subtle pt-6 text-xs text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5 text-success" />
              管理操作全程审计并受权限保护
            </div>
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
