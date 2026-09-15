import { useState } from 'react'
import { MessageSquare, RefreshCw, ShieldAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">
            Operations
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
            Control room
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Inspect supported operational state, review safe metadata, and take only
            backend-supported actions.
          </p>
        </div>
        <Button type="button" variant="outline" onClick={refresh} disabled={isLoading}>
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      </div>

      <div
        className="flex flex-wrap gap-2 border-b border-slate-200 pb-3"
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
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
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
      className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${active ? 'bg-slate-950 text-white' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'}`}
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
        <StatusMetric label="Sessions · 24h" value={summary?.total_sessions_24h ?? '—'} />
        <StatusMetric
          label="Average latency"
          value={
            summary?.avg_latency_ms_24h == null
              ? '—'
              : `${summary.avg_latency_ms_24h.toFixed(0)} ms`
          }
        />
        <StatusMetric
          label="Transfer rate"
          value={
            summary?.transfer_rate_24h == null
              ? '—'
              : `${(summary.transfer_rate_24h * 100).toFixed(1)}%`
          }
        />
        <StatusMetric
          label="Containment"
          value={
            summary?.containment_rate_24h == null
              ? '—'
              : `${(summary.containment_rate_24h * 100).toFixed(1)}%`
          }
        />
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <ShieldAlert className="h-5 w-5 text-amber-600" aria-hidden="true" />
            Active alerts
          </CardTitle>
        </CardHeader>
        <CardContent>
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
                  className="flex items-start justify-between gap-4 rounded-xl border p-4"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge variant={alert.severity === 'P0' ? 'destructive' : 'secondary'}>
                        {alert.severity}
                      </Badge>
                      <span className="font-medium">{alert.name}</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">{alert.message}</p>
                  </div>
                  <time className="text-xs text-slate-400">{formatDate(alert.fired_at)}</time>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function StatusMetric({
  label,
  value,
}: {
  label: string
  value: string | number
}): React.ReactElement {
  return (
    <Card>
      <CardContent className="p-5">
        <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p>
        <p className="mt-3 text-2xl font-semibold text-slate-950">{value}</p>
        <p className="mt-1 text-xs text-slate-500">Existing backend metric</p>
      </CardContent>
    </Card>
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
    <Card>
      <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <CardTitle className="text-lg">Review queue</CardTitle>
          <p className="mt-1 text-sm text-slate-500">
            Safe metadata only; customer content and order snapshots are intentionally omitted.
          </p>
        </div>
        <label className="text-sm text-slate-600">
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
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex flex-wrap gap-2 text-xs text-slate-500">
          <Badge variant="secondary">Total {stats?.total ?? 0}</Badge>
          <Badge variant="outline">High risk {stats?.risk_tasks ?? 0}</Badge>
          <Badge variant="outline">Confidence {stats?.confidence_tasks ?? 0}</Badge>
        </div>
        {tasks.length === 0 ? (
          <ConsoleEmptyState
            title="The review queue is empty"
            description="No pending review items match the current filter."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b text-xs uppercase tracking-wide text-slate-500">
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
                      <Badge variant={task.risk_level === 'HIGH' ? 'destructive' : 'secondary'}>
                        {task.risk_level}
                      </Badge>
                    </td>
                    <td className="px-3 py-3 font-medium text-slate-800">{task.trigger_reason}</td>
                    <td className="px-3 py-3 text-slate-500">User #{task.user_id}</td>
                    <td className="px-3 py-3 text-slate-500">{formatDate(task.created_at)}</td>
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
                        <span className="text-xs text-slate-400">Read only</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
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
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <MessageSquare className="h-5 w-5 text-indigo-600" aria-hidden="true" />
          Conversation metadata
        </CardTitle>
        <p className="mt-1 text-sm text-slate-500">
          Read-only operational metadata from the existing paginated conversation API. Message
          content is not loaded.
        </p>
      </CardHeader>
      <CardContent>
        <div className="mb-5 grid gap-3 md:grid-cols-2">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
            User reference
            <Input
              className="mt-1"
              inputMode="numeric"
              value={userFilter}
              onChange={(event) => onUserFilterChange(event.target.value)}
              placeholder="Filter by user ID"
            />
          </label>
          <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Intent category
            <Input
              className="mt-1"
              value={intentFilter}
              onChange={(event) => onIntentFilterChange(event.target.value)}
              placeholder="Filter by existing category"
            />
          </label>
        </div>
        {threads.length === 0 ? (
          <ConsoleEmptyState
            title="No conversations found"
            description="The current filters returned no conversation metadata."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b text-xs uppercase tracking-wide text-slate-500">
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
                    <td className="px-3 py-3 font-mono text-xs text-slate-700">
                      {thread.thread_id}
                    </td>
                    <td className="px-3 py-3 text-slate-500">
                      {thread.user_id == null ? '—' : `User #${thread.user_id}`}
                    </td>
                    <td className="px-3 py-3 text-slate-700">{thread.message_count}</td>
                    <td className="px-3 py-3 text-slate-500">{thread.intent_category ?? '—'}</td>
                    <td className="px-3 py-3 text-slate-500">{formatDate(thread.last_updated)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-5 flex items-center justify-between border-t pt-4">
          <p className="text-xs text-slate-500">
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
      </CardContent>
    </Card>
  )
}
