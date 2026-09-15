import { useState } from 'react'
import { ClipboardCheck, Database, ShieldCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/stores/auth'
import { hasCapability } from '@/lib/authorization'
import { getConsoleErrorMessage } from '@/lib/console-errors'
import {
  useApprovalDecisionMutation,
  useConsoleApprovals,
  useRetentionMutation,
} from '@/hooks/useEnterpriseConsole'
import {
  ConsoleEmptyState,
  ConsoleErrorState,
  ConsolePageSkeleton,
} from '../components/ConsoleState'
import { ConfirmDialog } from '../components/ConfirmDialog'

const RETENTION_DATASETS = [
  'message_cards',
  'message_feedbacks',
  'knowledge_documents',
  'sensitive_export_artifacts',
] as const

export function Compliance(): React.ReactElement {
  const { user } = useAuthStore()
  const canRead = hasCapability(user, 'compliance.read')
  const canApprove = hasCapability(user, 'exports.approve')
  const canManageRetention = hasCapability(user, 'compliance.manage')
  const approvals = useConsoleApprovals(canRead)
  const decisionMutation = useApprovalDecisionMutation()
  const retentionMutation = useRetentionMutation()
  const [pendingDecision, setPendingDecision] = useState<{
    approvalId: string
    decision: 'APPROVE' | 'REJECT'
  } | null>(null)
  const [dataset, setDataset] = useState<(typeof RETENTION_DATASETS)[number]>('message_cards')
  const [retentionResult, setRetentionResult] = useState<Awaited<
    ReturnType<typeof retentionMutation.mutateAsync>
  > | null>(null)
  const [previewDataset, setPreviewDataset] = useState<string | null>(null)
  const [confirmRetention, setConfirmRetention] = useState(false)
  const hasRetentionPreview = retentionResult?.dry_run === true && previewDataset === dataset

  if (approvals.isLoading) return <ConsolePageSkeleton />

  const submitDecision = (): void => {
    if (!pendingDecision) return
    decisionMutation.mutate(pendingDecision, { onSuccess: () => setPendingDecision(null) })
  }

  const previewRetention = (): void => {
    retentionMutation.mutate(
      { dataset, mode: 'dry-run' },
      {
        onSuccess: (result) => {
          setRetentionResult(result)
          setPreviewDataset(dataset)
        },
      }
    )
  }

  const executeRetention = (): void => {
    retentionMutation.mutate(
      { dataset, mode: 'execute' },
      {
        onSuccess: (result) => {
          setRetentionResult(result)
          setPreviewDataset(null)
          setConfirmRetention(false)
        },
      }
    )
  }

  return (
    <div className="space-y-7">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">
          Compliance
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
          Approvals and lifecycle controls
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          Handle only the exact approval metadata and bounded retention operations exposed by the
          backend. Export content is never rendered in this queue.
        </p>
      </div>

      {!canRead ? (
        <ConsoleEmptyState
          title="Compliance data is not available"
          description="This page requires compliance.read. Your authenticated session remains intact."
        />
      ) : approvals.error ? (
        <ConsoleErrorState error={approvals.error} onRetry={() => void approvals.refetch()} />
      ) : (
        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <ClipboardCheck className="h-5 w-5 text-indigo-600" aria-hidden="true" />
                Sensitive-operation approvals
              </CardTitle>
              <p className="mt-1 text-sm text-slate-500">
                Requester, type, hash, expiry, status, and decision metadata only.
              </p>
            </div>
            <Badge variant="outline">
              {approvals.data?.filter((approval) => approval.status === 'PENDING').length ?? 0}{' '}
              pending
            </Badge>
          </CardHeader>
          <CardContent>
            {approvals.data?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[880px] text-left text-sm">
                  <thead className="border-b text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-3 py-3">Operation</th>
                      <th className="px-3 py-3">Requester</th>
                      <th className="px-3 py-3">Status</th>
                      <th className="px-3 py-3">Requested / expiry</th>
                      <th className="px-3 py-3">Evidence</th>
                      <th className="px-3 py-3 text-right">Decision</th>
                    </tr>
                  </thead>
                  <tbody>
                    {approvals.data.map((approval) => (
                      <tr key={approval.id} className="border-b last:border-0">
                        <td className="px-3 py-4">
                          <p className="font-medium text-slate-800">{approval.operation_type}</p>
                          <p className="mt-1 font-mono text-[10px] text-slate-400">{approval.id}</p>
                        </td>
                        <td className="px-3 py-4 text-slate-600">
                          User #{approval.requester_user_id}
                        </td>
                        <td className="px-3 py-4">
                          <Badge variant={approval.status === 'PENDING' ? 'secondary' : 'outline'}>
                            {approval.status}
                          </Badge>
                        </td>
                        <td className="px-3 py-4 text-xs text-slate-500">
                          <div>{new Date(approval.requested_at).toLocaleString()}</div>
                          <div className="mt-1">
                            Expires {new Date(approval.expires_at).toLocaleString()}
                          </div>
                        </td>
                        <td className="px-3 py-4">
                          <span className="font-mono text-xs text-slate-500" title="Payload hash">
                            {approval.operation_payload_hash.slice(0, 12)}…
                          </span>
                          <span className="ml-2 text-xs text-slate-400">
                            {Object.keys(approval.operation_parameters).length} safe parameter
                            fields
                          </span>
                        </td>
                        <td className="px-3 py-4 text-right">
                          {canApprove && approval.status === 'PENDING' ? (
                            <div className="flex justify-end gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={decisionMutation.isPending}
                                onClick={() =>
                                  setPendingDecision({
                                    approvalId: approval.id,
                                    decision: 'REJECT',
                                  })
                                }
                              >
                                Reject
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                disabled={decisionMutation.isPending}
                                onClick={() =>
                                  setPendingDecision({
                                    approvalId: approval.id,
                                    decision: 'APPROVE',
                                  })
                                }
                              >
                                Approve
                              </Button>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">
                              {canApprove ? 'No action' : 'Read only'}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <ConsoleEmptyState
                title="No approvals returned"
                description="The tenant approval queue is empty. New requests must come from the accepted export-request flow."
              />
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Database className="h-5 w-5 text-indigo-600" aria-hidden="true" />
            Bounded retention operation
          </CardTitle>
          <p className="mt-1 text-sm text-slate-500">
            Preview eligibility first. Execution is tenant-bound, batch-limited, audited, and
            available only to compliance.manage.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="text-sm font-medium text-slate-700">
              Dataset
              <select
                aria-label="Retention dataset"
                value={dataset}
                onChange={(event) =>
                  setDataset(event.target.value as (typeof RETENTION_DATASETS)[number])
                }
                className="mt-1 block h-9 w-full rounded-md border border-input bg-background px-3 text-sm sm:w-72"
              >
                {RETENTION_DATASETS.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={!canRead || retentionMutation.isPending}
                onClick={previewRetention}
              >
                Preview eligible records
              </Button>
              <Button
                type="button"
                variant="destructive"
                disabled={
                  !canManageRetention || !hasRetentionPreview || retentionMutation.isPending
                }
                onClick={() => setConfirmRetention(true)}
              >
                Execute bounded batch
              </Button>
            </div>
          </div>
          {canManageRetention && !hasRetentionPreview && (
            <p className="text-xs text-slate-500">
              Run a preview for the selected dataset before execution is enabled.
            </p>
          )}
          {!canManageRetention && (
            <p className="text-xs text-slate-500">
              Execution controls are hidden from sessions without compliance.manage.
            </p>
          )}
          {retentionResult && (
            <div
              role="status"
              className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"
            >
              <div className="flex items-center gap-2 font-medium">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                {retentionResult.dry_run ? 'Dry run complete' : 'Retention batch complete'}
              </div>
              <p className="mt-2 text-xs">
                Dataset: {retentionResult.dataset} · Eligible: {retentionResult.eligible_count} ·
                Processed: {retentionResult.processed_count} · Failed:{' '}
                {retentionResult.failed_count}
              </p>
            </div>
          )}
          {retentionMutation.error && (
            <p
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              {getConsoleErrorMessage(retentionMutation.error)}
            </p>
          )}
        </CardContent>
      </Card>

      {decisionMutation.error && (
        <p
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {getConsoleErrorMessage(decisionMutation.error)}
        </p>
      )}

      <ConfirmDialog
        open={pendingDecision !== null}
        title={
          pendingDecision?.decision === 'APPROVE'
            ? 'Approve sensitive operation?'
            : 'Reject sensitive operation?'
        }
        description={`This records a ${pendingDecision?.decision?.toLowerCase() ?? 'new'} decision for approval ${pendingDecision?.approvalId ?? '—'}. The backend will enforce expiry and requester separation.`}
        confirmLabel={
          pendingDecision?.decision === 'APPROVE' ? 'Approve operation' : 'Reject operation'
        }
        destructive={pendingDecision?.decision === 'REJECT'}
        pending={decisionMutation.isPending}
        onOpenChange={(open) => {
          if (!open && !decisionMutation.isPending) setPendingDecision(null)
        }}
        onConfirm={submitDecision}
      />
      <ConfirmDialog
        open={confirmRetention}
        title="Execute bounded retention batch?"
        description={`This will request the backend to process one bounded tenant-local retention batch for ${dataset}. It may delete eligible records and will create compliance evidence.`}
        confirmLabel="Execute retention"
        destructive
        pending={retentionMutation.isPending}
        onOpenChange={(open) => {
          if (!open && !retentionMutation.isPending) setConfirmRetention(false)
        }}
        onConfirm={executeRetention}
      />
    </div>
  )
}
