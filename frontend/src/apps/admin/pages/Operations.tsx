import { useState } from 'react'
import { Activity, Clock, Gauge, MessageSquare, Radio, RefreshCw, ShieldAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/stores/auth'
import { hasCapability } from '@/lib/authorization'
import {
  useActiveConsoleAlerts,
  useConsoleConversations,
  useConsoleReviewTasks,
  useConsoleSummary,
  useConsoleTaskStats,
  useReviewDecisionMutation,
} from '@/hooks/useEnterpriseConsole'
import { getConsoleErrorMessage } from '@/lib/console-errors'
import {
  ConsoleEmptyState,
  ConsoleErrorState,
  ConsolePageSkeleton,
} from '../components/ConsoleState'
import { ConfirmDialog } from '../components/ConfirmDialog'
import {
  adminTableClassName,
  DataPanel,
  DataTableShell,
  FilterBar,
  MetricCard,
  PageHeader,
  SectionHeader,
  StatusBadge,
} from '../components/AdminPrimitives'

type OperationsTab = 'status' | 'reviews' | 'conversations'

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
}

export function Operations(): React.ReactElement {
  const { user } = useAuthStore()
  const canOperate = hasCapability(user, 'operations.read')
  const canReview = hasCapability(user, 'reviews.read')
  const canDecide = hasCapability(user, 'refunds.approve')
  const canReadConversations = hasCapability(user, 'conversations.read')
  const [tab, setTab] = useState<OperationsTab>(
    canOperate ? 'status' : canReview ? 'reviews' : 'conversations'
  )
  const [riskLevel, setRiskLevel] = useState<'HIGH' | 'MEDIUM' | 'LOW' | undefined>()
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [decision, setDecision] = useState<'APPROVE' | 'REJECT' | null>(null)
  const [userFilter, setUserFilter] = useState('')
  const [intentFilter, setIntentFilter] = useState('')
  const [offset, setOffset] = useState(0)

  const summary = useConsoleSummary(canOperate)
  const alerts = useActiveConsoleAlerts(canOperate)
  const taskStats = useConsoleTaskStats(canReview)
  const tasks = useConsoleReviewTasks({ risk_level: riskLevel }, canReview)
  const conversations = useConsoleConversations(
    { user_id: userFilter || undefined, intent_category: intentFilter || undefined },
    offset,
    20,
    canReadConversations
  )
  const decisionMutation = useReviewDecisionMutation()

  const isLoading =
    (tab === 'status' && (summary.isLoading || alerts.isLoading)) ||
    (tab === 'reviews' && (taskStats.isLoading || tasks.isLoading)) ||
    (tab === 'conversations' && conversations.isLoading)

  const activeError =
    tab === 'status'
      ? (summary.error ?? alerts.error)
      : tab === 'reviews'
        ? (taskStats.error ?? tasks.error)
        : conversations.error

  const refresh = (): void => {
    if (tab === 'status') {
      void summary.refetch()
      void alerts.refetch()
    } else if (tab === 'reviews') {
      void taskStats.refetch()
      void tasks.refetch()
    } else {
      void conversations.refetch()
    }
  }

  const submitDecision = (): void => {
    if (selectedTaskId === null || decision === null) return
    decisionMutation.mutate(
      { auditLogId: selectedTaskId, action: decision },
      {
        onSuccess: () => {
          setSelectedTaskId(null)
          setDecision(null)
        },
      }
    )
  }

  if (isLoading) return <ConsolePageSkeleton />

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Operations"
        title="Control room"
        description="Track runtime posture, review queues, active alerts, and conversation execution using safe operational metadata."
        status={
          <StatusBadge tone="success" pulse>
            Live operational surface
          </StatusBadge>
        }
        actions={
          <Button type="button" variant="outline" onClick={refresh} disabled={isLoading}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </Button>
        }
      />

      <div
        className="flex w-fit max-w-full flex-wrap gap-1 rounded-md border border-border-subtle bg-muted/55 p-1"
        role="tablist"
        aria-label="Operations views"
      >
        {canOperate && (
          <TabButton
            active={tab === 'status'}
            onClick={() => setTab('status')}
            label="System status"
          />
        )}
        {canReview && (
          <TabButton
            active={tab === 'reviews'}
            onClick={() => setTab('reviews')}
            label="Review queue"
          />
        )}
        {canReadConversations && (
          <TabButton
            active={tab === 'conversations'}
            onClick={() => setTab('conversations')}
            label="Conversation metadata"
          />
        )}
      </div>

      {activeError ? (
        <ConsoleErrorState error={activeError} onRetry={refresh} />
      ) : tab === 'status' ? (
        <StatusPanel summary={summary.data} alerts={alerts.data ?? []} />
      ) : tab === 'reviews' ? (
        <ReviewPanel
          canDecide={canDecide}
          tasks={tasks.data ?? []}
          stats={taskStats.data}
          riskLevel={riskLevel}
          onRiskLevelChange={setRiskLevel}
          onSelect={(taskId, action) => {
            setSelectedTaskId(taskId)
            setDecision(action)
          }}
          isMutating={decisionMutation.isPending}
        />
      ) : (
        <ConversationPanel
          threads={conversations.data?.threads ?? []}
          total={conversations.data?.total ?? 0}
          offset={offset}
          userFilter={userFilter}
          intentFilter={intentFilter}
          onUserFilterChange={(value) => {
            setUserFilter(value)
            setOffset(0)
          }}
          onIntentFilterChange={(value) => {
            setIntentFilter(value)
            setOffset(0)
          }}
          onPrevious={() => setOffset((value) => Math.max(0, value - 20))}
          onNext={() => setOffset((value) => value + 20)}
        />
      )}

      {decisionMutation.error && (
        <p
          role="alert"
          className="rounded-md border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger"
        >
          {getConsoleErrorMessage(decisionMutation.error)}
        </p>
      )}

      <ConfirmDialog
        open={selectedTaskId !== null && decision !== null}
        title={decision === 'APPROVE' ? 'Approve review decision?' : 'Reject review decision?'}
        description={`This will submit ${decision?.toLowerCase() ?? 'the selected'} decision for review item #${selectedTaskId ?? '—'}. The backend will apply its current authorization and lifecycle checks.`}
        confirmLabel={decision === 'APPROVE' ? 'Approve decision' : 'Reject decision'}
        destructive={decision === 'REJECT'}
        pending={decisionMutation.isPending}
        onOpenChange={(open) => {
          if (!open && !decisionMutation.isPending) {
            setSelectedTaskId(null)
            setDecision(null)
          }
        }}
        onConfirm={submitDecision}
      />
    </div>
  )
}

function TabButton({
  active,
  onClick,
  label,
}: {
  active: boolean
  onClick: () => void
  label: string
}): React.ReactElement {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`rounded-sm px-3 py-2 text-sm font-medium transition-colors ${active ? 'bg-surface-elevated text-foreground shadow-sm' : 'text-muted-foreground hover:bg-surface/70 hover:text-foreground'}`}
    >
      {label}
    </button>
  )
}

function StatusPanel({
  summary,
  alerts,
}: {
  summary: ReturnType<typeof useConsoleSummary>['data']
  alerts: NonNullable<ReturnType<typeof useActiveConsoleAlerts>['data']>
}): React.ReactElement {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Sessions · 24h"
          value={summary?.total_sessions_24h ?? '—'}
          detail="Existing backend metric"
          icon={Activity}
        />
        <MetricCard
          label="Average latency"
          value={
            summary?.avg_latency_ms_24h == null
              ? '—'
              : `${summary.avg_latency_ms_24h.toFixed(0)} ms`
          }
          detail="Existing backend metric"
          icon={Clock}
        />
        <MetricCard
          label="Transfer rate"
          value={
            summary?.transfer_rate_24h == null
              ? '—'
              : `${(summary.transfer_rate_24h * 100).toFixed(1)}%`
          }
          detail="Existing backend metric"
          icon={Radio}
        />
        <MetricCard
          label="Containment"
          value={
            summary?.containment_rate_24h == null
              ? '—'
              : `${(summary.containment_rate_24h * 100).toFixed(1)}%`
          }
          detail="Existing backend metric"
          icon={Gauge}
          tone="success"
        />
      </div>
      <DataPanel className="p-5">
        <SectionHeader
          title="Active alerts"
          description="Current alert events from the operational endpoint."
          icon={ShieldAlert}
        />
        <div className="mt-5">
          {alerts.length === 0 ? (
            <ConsoleEmptyState
              title="No active alerts"
              description="The existing alert endpoint reports a clear state."
            />
          ) : (
            <div className="space-y-3">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="flex items-start justify-between gap-4 rounded-md border border-border-subtle bg-surface-elevated/45 p-4"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <StatusBadge tone={alert.severity === 'P0' ? 'danger' : 'warning'}>
                        {alert.severity}
                      </StatusBadge>
                      <span className="font-medium">{alert.name}</span>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{alert.message}</p>
                  </div>
                  <time className="numeric text-xs text-muted-foreground">
                    {formatDate(alert.fired_at)}
                  </time>
                </div>
              ))}
            </div>
          )}
        </div>
      </DataPanel>
    </div>
  )
}

function ReviewPanel({
  canDecide,
  tasks,
  stats,
  riskLevel,
  onRiskLevelChange,
  onSelect,
  isMutating,
}: {
  canDecide: boolean
  tasks: import('@/types').Task[]
  stats: ReturnType<typeof useConsoleTaskStats>['data']
  riskLevel: 'HIGH' | 'MEDIUM' | 'LOW' | undefined
  onRiskLevelChange: (level: 'HIGH' | 'MEDIUM' | 'LOW' | undefined) => void
  onSelect: (taskId: number, action: 'APPROVE' | 'REJECT') => void
  isMutating: boolean
}): React.ReactElement {
  return (
    <DataPanel className="p-5">
      <SectionHeader
        title="Review queue"
        description="Safe metadata only; customer content and order snapshots are intentionally omitted."
        icon={ShieldAlert}
      />
      <FilterBar className="mt-5">
        <label className="text-sm text-muted-foreground">
          Risk filter
          <select
            aria-label="Risk filter"
            value={riskLevel ?? ''}
            onChange={(event) =>
              onRiskLevelChange(
                (event.target.value || undefined) as 'HIGH' | 'MEDIUM' | 'LOW' | undefined
              )
            }
            className="ml-2 h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">All</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </label>
        <div className="flex flex-wrap gap-2 sm:ml-auto">
          <StatusBadge>Total {stats?.total ?? 0}</StatusBadge>
          <StatusBadge tone="danger">High risk {stats?.risk_tasks ?? 0}</StatusBadge>
          <StatusBadge tone="info">Confidence {stats?.confidence_tasks ?? 0}</StatusBadge>
        </div>
      </FilterBar>
      <div className="mt-5">
        {tasks.length === 0 ? (
          <ConsoleEmptyState
            title="The review queue is empty"
            description="No pending review items match the current filter."
          />
        ) : (
          <DataTableShell>
            <table className={adminTableClassName}>
              <thead>
                <tr>
                  <th className="px-3 py-3">Risk</th>
                  <th className="px-3 py-3">Trigger</th>
                  <th className="px-3 py-3">User reference</th>
                  <th className="px-3 py-3">Created</th>
                  <th className="px-3 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.audit_log_id} className="border-b last:border-0">
                    <td className="px-3 py-3">
                      <StatusBadge
                        tone={
                          task.risk_level === 'HIGH'
                            ? 'danger'
                            : task.risk_level === 'MEDIUM'
                              ? 'warning'
                              : 'neutral'
                        }
                      >
                        {task.risk_level}
                      </StatusBadge>
                    </td>
                    <td className="font-medium text-foreground">{task.trigger_reason}</td>
                    <td className="text-muted-foreground">User #{task.user_id}</td>
                    <td className="numeric text-muted-foreground">{formatDate(task.created_at)}</td>
                    <td className="px-3 py-3 text-right">
                      {canDecide ? (
                        <div className="flex justify-end gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={isMutating}
                            onClick={() => onSelect(task.audit_log_id, 'REJECT')}
                          >
                            Reject
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            disabled={isMutating}
                            onClick={() => onSelect(task.audit_log_id, 'APPROVE')}
                          >
                            Approve
                          </Button>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">Read only</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </DataTableShell>
        )}
      </div>
    </DataPanel>
  )
}

function ConversationPanel({
  threads,
  total,
  offset,
  userFilter,
  intentFilter,
  onUserFilterChange,
  onIntentFilterChange,
  onPrevious,
  onNext,
}: {
  threads: import('@/types').ConversationThread[]
  total: number
  offset: number
  userFilter: string
  intentFilter: string
  onUserFilterChange: (value: string) => void
  onIntentFilterChange: (value: string) => void
  onPrevious: () => void
  onNext: () => void
}): React.ReactElement {
  return (
    <DataPanel className="p-5">
      <SectionHeader
        title="Conversation metadata"
        description="Read-only operational metadata from the existing paginated conversation API. Message content is not loaded."
        icon={MessageSquare}
      />
      <FilterBar className="mt-5 grid md:grid-cols-2">
        <label className="text-caption uppercase text-muted-foreground">
          User reference
          <Input
            className="mt-1"
            inputMode="numeric"
            value={userFilter}
            onChange={(event) => onUserFilterChange(event.target.value)}
            placeholder="Filter by user ID"
          />
        </label>
        <label className="text-caption uppercase text-muted-foreground">
          Intent category
          <Input
            className="mt-1"
            value={intentFilter}
            onChange={(event) => onIntentFilterChange(event.target.value)}
            placeholder="Filter by existing category"
          />
        </label>
      </FilterBar>
      <div className="mt-5">
        {threads.length === 0 ? (
          <ConsoleEmptyState
            title="No conversations found"
            description="The current filters returned no conversation metadata."
          />
        ) : (
          <DataTableShell>
            <table className={adminTableClassName}>
              <thead>
                <tr>
                  <th className="px-3 py-3">Conversation</th>
                  <th className="px-3 py-3">User reference</th>
                  <th className="px-3 py-3">Messages</th>
                  <th className="px-3 py-3">Intent</th>
                  <th className="px-3 py-3">Last activity</th>
                </tr>
              </thead>
              <tbody>
                {threads.map((thread) => (
                  <tr key={thread.thread_id} className="border-b last:border-0">
                    <td className="font-mono text-xs text-foreground">{thread.thread_id}</td>
                    <td className="text-muted-foreground">
                      {thread.user_id == null ? '—' : `User #${thread.user_id}`}
                    </td>
                    <td className="numeric text-foreground">{thread.message_count}</td>
                    <td className="text-muted-foreground">{thread.intent_category ?? '—'}</td>
                    <td className="numeric text-muted-foreground">
                      {formatDate(thread.last_updated)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </DataTableShell>
        )}
        <div className="mt-5 flex items-center justify-between border-t border-border-subtle pt-4">
          <p className="numeric text-xs text-muted-foreground">
            Showing {total === 0 ? 0 : offset + 1}–{Math.min(offset + 20, total)} of {total}
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={onPrevious}
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={offset + 20 >= total}
              onClick={onNext}
            >
              Next
            </Button>
          </div>
        </div>
      </div>
    </DataPanel>
  )
}
