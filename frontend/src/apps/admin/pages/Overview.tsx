import { Link } from 'react-router-dom'
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  ShieldAlert,
  Users,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/stores/auth'
import { hasAnyCapability, hasCapability } from '@/lib/authorization'
import {
  useActiveConsoleAlerts,
  useConsoleApprovals,
  useConsoleMemberships,
  useConsoleSummary,
  useConsoleTaskStats,
} from '@/hooks/useEnterpriseConsole'
import {
  ConsoleEmptyState,
  ConsoleErrorState,
  ConsolePageSkeleton,
} from '../components/ConsoleState'

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = 'indigo',
}: {
  label: string
  value: string | number
  detail: string
  icon: typeof Activity
  tone?: 'indigo' | 'amber' | 'emerald' | 'rose'
}): React.ReactElement {
  const toneClasses = {
    indigo: 'bg-indigo-50 text-indigo-700',
    amber: 'bg-amber-50 text-amber-700',
    emerald: 'bg-emerald-50 text-emerald-700',
    rose: 'bg-rose-50 text-rose-700',
  }
  return (
    <Card className="border-slate-200/80 shadow-sm">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">
              {label}
            </p>
            <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">{value}</p>
            <p className="mt-1 text-xs text-slate-500">{detail}</p>
          </div>
          <div className={`grid h-10 w-10 place-items-center rounded-xl ${toneClasses[tone]}`}>
            <Icon className="h-5 w-5" aria-hidden="true" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function Overview(): React.ReactElement {
  const { user } = useAuthStore()
  const canOperate = hasCapability(user, 'operations.read')
  const canReview = hasCapability(user, 'reviews.read')
  const canApprove = hasCapability(user, 'compliance.read')
  const canSeeIdentity = hasCapability(user, 'identity.read')
  const hasOverviewSource = hasAnyCapability(user, [
    'operations.read',
    'reviews.read',
    'compliance.read',
    'identity.read',
    'conversations.read',
  ])

  const summary = useConsoleSummary(canOperate)
  const taskStats = useConsoleTaskStats(canReview)
  const alerts = useActiveConsoleAlerts(canOperate)
  const approvals = useConsoleApprovals(canApprove)
  const memberships = useConsoleMemberships(canSeeIdentity)

  if (!hasOverviewSource) {
    return (
      <div className="py-12">
        <ConsoleEmptyState
          title="No overview data is available for this session"
          description="Your current capabilities do not include an operational console source. Ask a tenant administrator for the appropriate read capability."
        />
      </div>
    )
  }

  const sources = [summary, taskStats, alerts, approvals, memberships].filter(
    (query) => query.isEnabled
  )
  if (sources.some((query) => query.isLoading)) return <ConsolePageSkeleton />

  const firstError = sources.find((query) => query.error)?.error
  if (firstError) {
    return (
      <div className="space-y-6">
        <PageIntro />
        <ConsoleErrorState
          error={firstError}
          onRetry={() => void Promise.all(sources.map((query) => query.refetch()))}
        />
      </div>
    )
  }

  const pendingApprovals = approvals.data?.filter(
    (approval) => approval.status === 'PENDING'
  ).length
  const criticalAlerts = alerts.data?.filter(
    (alert) => alert.severity === 'P0' || alert.severity === 'P1'
  ).length

  return (
    <div className="space-y-7">
      <PageIntro />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Sessions · 24h"
          value={canOperate ? (summary.data?.total_sessions_24h ?? '—') : '—'}
          detail={canOperate ? 'Existing operational metric' : 'Requires operations.read'}
          icon={Activity}
        />
        <MetricCard
          label="Review queue"
          value={canReview ? (taskStats.data?.total ?? '—') : '—'}
          detail={
            canReview
              ? `${taskStats.data?.risk_tasks ?? 0} high-risk items`
              : 'Requires reviews.read'
          }
          icon={ClipboardCheck}
          tone="amber"
        />
        <MetricCard
          label="Active alerts"
          value={canOperate ? (alerts.data?.length ?? 0) : '—'}
          detail={
            canOperate
              ? `${criticalAlerts ?? 0} P0/P1 requiring attention`
              : 'Requires operations.read'
          }
          icon={ShieldAlert}
          tone={criticalAlerts ? 'rose' : 'emerald'}
        />
        <MetricCard
          label="Pending approvals"
          value={canApprove ? (pendingApprovals ?? 0) : '—'}
          detail={canApprove ? 'Sensitive operations only' : 'Requires compliance.read'}
          icon={Users}
          tone="indigo"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <Card className="border-slate-200/80 shadow-sm">
          <CardHeader className="flex-row items-start justify-between space-y-0">
            <div>
              <CardTitle className="text-lg">Attention queue</CardTitle>
              <p className="mt-1 text-sm text-slate-500">
                Only current backend states are shown here.
              </p>
            </div>
            <Button type="button" variant="outline" size="sm" asChild>
              <Link to="/operations">
                Open operations <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {canOperate && alerts.data && alerts.data.length > 0 ? (
              <div className="space-y-3">
                {alerts.data.slice(0, 5).map((alert) => (
                  <div
                    key={alert.id}
                    className="flex items-start justify-between gap-4 rounded-xl border border-slate-200 p-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge variant={alert.severity === 'P0' ? 'destructive' : 'secondary'}>
                          {alert.severity}
                        </Badge>
                        <p className="truncate text-sm font-medium text-slate-800">{alert.name}</p>
                      </div>
                      <p className="mt-1 text-sm text-slate-600">{alert.message}</p>
                    </div>
                    <time className="shrink-0 text-xs text-slate-400">
                      {formatDate(alert.fired_at)}
                    </time>
                  </div>
                ))}
              </div>
            ) : canReview && taskStats.data && taskStats.data.total > 0 ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
                {taskStats.data.total} review items are waiting for an authorized operator.
              </div>
            ) : (
              <ConsoleEmptyState
                title="No active attention items"
                description="The supported operational sources are currently clear."
              />
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-200/80 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Access-aware next steps</CardTitle>
            <p className="mt-1 text-sm text-slate-500">
              Navigate only to surfaces your current session can use.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {canSeeIdentity && (
              <QuickLink
                href="/security"
                label="Review tenant access"
                detail="Memberships and effective capabilities"
                icon={Users}
              />
            )}
            {canApprove && (
              <QuickLink
                href="/compliance"
                label="Process approvals"
                detail="Keep requester and approver separate"
                icon={ClipboardCheck}
              />
            )}
            {canOperate && (
              <QuickLink
                href="/ai"
                label="Review AI configuration"
                detail="Agent settings and version history"
                icon={CheckCircle2}
              />
            )}
            {!canSeeIdentity && !canApprove && !canOperate && (
              <p className="text-sm text-slate-500">
                No additional console links are available for this session.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function PageIntro(): React.ReactElement {
  return (
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">
          Command center
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
          Operational overview
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          A quiet, evidence-first view of supported system state. Counts are sourced from existing
          APIs and show “—” when this session cannot read a domain.
        </p>
      </div>
      <Badge variant="outline" className="w-fit border-emerald-200 bg-emerald-50 text-emerald-700">
        Server-authoritative session
      </Badge>
    </div>
  )
}

function QuickLink({
  href,
  label,
  detail,
  icon: Icon,
}: {
  href: string
  label: string
  detail: string
  icon: typeof Users
}): React.ReactElement {
  return (
    <Button
      type="button"
      variant="ghost"
      className="h-auto w-full justify-between rounded-xl border border-slate-200 p-3 text-left hover:bg-slate-50"
      asChild
    >
      <Link to={href}>
        <span className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-slate-100 text-slate-600">
            <Icon className="h-4 w-4" aria-hidden="true" />
          </span>
          <span>
            <span className="block text-sm font-medium text-slate-800">{label}</span>
            <span className="mt-0.5 block text-xs text-slate-500">{detail}</span>
          </span>
        </span>
        <ArrowRight className="h-4 w-4 text-slate-400" aria-hidden="true" />
      </Link>
    </Button>
  )
}
