import { Link } from 'react-router-dom'
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  ShieldAlert,
  Users,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
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
import {
  DataPanel,
  MetricCard,
  PageHeader,
  SectionHeader,
  StatusBadge,
} from '../components/AdminPrimitives'

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
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
      <div className="space-y-7">
        <OverviewHeader />
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
      <OverviewHeader />

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
          tone="warning"
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
          tone={criticalAlerts ? 'danger' : 'success'}
        />
        <MetricCard
          label="Pending approvals"
          value={canApprove ? (pendingApprovals ?? 0) : '—'}
          detail={canApprove ? 'Sensitive operations only' : 'Requires compliance.read'}
          icon={Users}
          tone="info"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <DataPanel className="p-5">
          <SectionHeader
            title="Work requiring attention"
            description="Current backend states, ordered for operator review."
            icon={ShieldAlert}
            action={
              <Button type="button" variant="outline" size="sm" asChild>
                <Link to="/operations">
                  Open operations <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </Link>
              </Button>
            }
          />
          <div className="mt-5">
            {canOperate && alerts.data && alerts.data.length > 0 ? (
              <div className="space-y-3">
                {alerts.data.slice(0, 5).map((alert) => (
                  <div
                    key={alert.id}
                    className="flex items-start justify-between gap-4 rounded-md border border-border-subtle bg-surface-elevated/55 p-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <StatusBadge tone={alert.severity === 'P0' ? 'danger' : 'warning'}>
                          {alert.severity}
                        </StatusBadge>
                        <p className="truncate text-sm font-medium text-foreground">{alert.name}</p>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">{alert.message}</p>
                    </div>
                    <time className="numeric shrink-0 text-xs text-muted-foreground">
                      {formatDate(alert.fired_at)}
                    </time>
                  </div>
                ))}
              </div>
            ) : canReview && taskStats.data && taskStats.data.total > 0 ? (
              <div className="rounded-md border border-warning/20 bg-warning/10 p-4 text-sm text-foreground">
                {taskStats.data.total} review items are waiting for an authorized operator.
              </div>
            ) : (
              <ConsoleEmptyState
                title="No active attention items"
                description="The supported operational sources are currently clear."
              />
            )}
          </div>
        </DataPanel>

        <DataPanel className="p-5">
          <SectionHeader
            title="Access-aware next steps"
            description="Available control-plane actions for this session."
            icon={CheckCircle2}
          />
          <div className="mt-5 space-y-2">
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
              <p className="text-sm text-muted-foreground">
                No additional console links are available for this session.
              </p>
            )}
          </div>
        </DataPanel>
      </div>
    </div>
  )
}

function OverviewHeader(): React.ReactElement {
  return (
    <PageHeader
      eyebrow="Command center"
      title="Operational overview"
      description="See what is happening, what needs attention, and whether the AI service is healthy. Every value comes from an existing backend source."
      status={<StatusBadge tone="success">Server-authoritative session</StatusBadge>}
    />
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
      className="h-auto w-full justify-between rounded-md border border-border-subtle bg-surface-elevated/35 p-3 text-left hover:bg-muted/45"
      asChild
    >
      <Link to={href}>
        <span className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-md bg-muted text-muted-foreground">
            <Icon className="h-4 w-4" aria-hidden="true" />
          </span>
          <span>
            <span className="block text-sm font-medium text-foreground">{label}</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">{detail}</span>
          </span>
        </span>
        <ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </Link>
    </Button>
  )
}
