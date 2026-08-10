import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Loader2, LockKeyhole, ShieldCheck } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { StarWarehouseLogo } from '@/components/brand/StarWarehouseLogo'
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
    <main className="relative grid min-h-screen overflow-hidden bg-slate-950 lg:grid-cols-[1fr_520px]">
      <section className="relative hidden overflow-hidden p-14 text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(99,102,241,0.38),transparent_34%),radial-gradient(circle_at_80%_80%,rgba(34,211,238,0.18),transparent_30%)]" />
        <div className="star-grid absolute inset-0 opacity-20" />
        <StarWarehouseLogo inverse className="relative" />
        <div className="relative my-auto max-w-xl">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-300">
            AI Customer Service OS
          </p>
          <h1 className="mt-5 text-5xl font-semibold leading-tight tracking-tight">
            看见每一次服务，
            <br />
            掌控每一个关键决策
          </h1>
          <p className="mt-6 max-w-lg text-base leading-8 text-slate-300">
            从知识治理、Agent
            配置到风险审核与质量评估，星仓AI为运营团队提供统一、可信、可追溯的工作空间。
          </p>
          <div className="mt-10 space-y-4">
            {['全链路服务质量观测', '高风险操作人工审核', '企业知识与策略统一治理'].map((item) => (
              <div key={item} className="flex items-center gap-3 text-sm text-slate-300">
                <CheckCircle2 className="h-4 w-4 text-cyan-300" />
                {item}
              </div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-slate-600">Star Warehouse AI · Enterprise Edition</p>
      </section>

      <section className="relative flex items-center justify-center bg-[#f7f8fc] px-5 py-10 lg:px-12">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_10%,rgba(99,102,241,0.12),transparent_26%)]" />
        <Card className="relative w-full max-w-md border-white bg-white/90 shadow-2xl shadow-slate-900/10 backdrop-blur-xl">
          <CardContent className="p-7 sm:p-10">
            <StarWarehouseLogo className="mb-10 lg:hidden" />
            <div className="mb-8">
              <div className="mb-5 grid h-12 w-12 place-items-center rounded-2xl bg-indigo-50 text-indigo-600">
                <LockKeyhole className="h-5 w-5" />
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-slate-950">登录运营中心</h2>
              <p className="mt-2 text-sm text-slate-500">仅授权的企业管理员可以访问</p>
            </div>
            <form onSubmit={(event) => void handleSubmit(event)} className="space-y-5">
              {error && (
                <Alert variant="destructive" className="rounded-xl">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <div className="space-y-2">
                <label htmlFor="admin-username" className="text-sm font-medium text-slate-700">
                  管理员账号
                </label>
                <Input
                  id="admin-username"
                  type="text"
                  placeholder="请输入管理员账号"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  className="h-12 bg-slate-50/80"
                  autoComplete="username"
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="admin-password" className="text-sm font-medium text-slate-700">
                  登录密码
                </label>
                <Input
                  id="admin-password"
                  type="password"
                  placeholder="请输入登录密码"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="h-12 bg-slate-50/80"
                  autoComplete="current-password"
                  required
                />
              </div>
              <Button
                type="submit"
                className="h-12 w-full rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 shadow-lg shadow-indigo-200"
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
            <div className="mt-8 flex items-center justify-center gap-2 border-t pt-6 text-xs text-slate-400">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
              管理操作全程审计并受权限保护
            </div>
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
