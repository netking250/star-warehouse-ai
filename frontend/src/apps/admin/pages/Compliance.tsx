import { useState } from 'react'
import { ClipboardCheck, Database, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
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
import {
  adminTableClassName,
  DataPanel,
  DataTableShell,
  FilterBar,
  PageHeader,
  SectionHeader,
  StatusBadge,
} from '../components/AdminPrimitives'

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
      <PageHeader
        eyebrow="Compliance"
        title="Approvals and lifecycle controls"
        description="Govern sensitive operations and bounded retention using auditable backend controls. Export content is never rendered in this queue."
        status={<StatusBadge tone="info">Evidence-first governance</StatusBadge>}
      />

      {!canRead ? (
        <ConsoleEmptyState
          title="Compliance data is not available"
          description="This page requires compliance.read. Your authenticated session remains intact."
        />
      ) : approvals.error ? (
        <ConsoleErrorState error={approvals.error} onRetry={() => void approvals.refetch()} />
      ) : (
        <DataPanel className="p-5">
          <SectionHeader
            title="Sensitive-operation approvals"
            description="Requester, type, hash, expiry, status, and decision metadata only."
            icon={ClipboardCheck}
            action={
              <StatusBadge tone="warning">
                {approvals.data?.filter((approval) => approval.status === 'PENDING').length ?? 0}{' '}
                pending
              </StatusBadge>
            }
          />
          <div className="mt-5">
            {approvals.data?.length ? (
              <DataTableShell>
                <table className={`${adminTableClassName} min-w-[880px]`}>
                  <thead>
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
                          <p className="font-medium text-foreground">{approval.operation_type}</p>
                          <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                            {approval.id}
                          </p>
                        </td>
                        <td className="text-muted-foreground">
                          User #{approval.requester_user_id}
                        </td>
                        <td className="px-3 py-4">
                          <StatusBadge
                            tone={
                              approval.status === 'PENDING'
                                ? 'warning'
                                : approval.status === 'APPROVED'
                                  ? 'success'
                                  : 'neutral'
                            }
                          >
                            {approval.status}
                          </StatusBadge>
                        </td>
                        <td className="numeric text-xs text-muted-foreground">
                          <div>{new Date(approval.requested_at).toLocaleString()}</div>
                          <div className="mt-1">
                            Expires {new Date(approval.expires_at).toLocaleString()}
                          </div>
                        </td>
                        <td className="px-3 py-4">
                          <span
                            className="font-mono text-xs text-muted-foreground"
                            title="Payload hash"
                          >
                            {approval.operation_payload_hash.slice(0, 12)}…
                          </span>
                          <span className="ml-2 text-xs text-muted-foreground">
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
                            <span className="text-xs text-muted-foreground">
                              {canApprove ? 'No action' : 'Read only'}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </DataTableShell>
            ) : (
              <ConsoleEmptyState
                title="No approvals returned"
                description="The tenant approval queue is empty. New requests must come from the accepted export-request flow."
              />
            )}
          </div>
        </DataPanel>
      )}

      <DataPanel className="p-5">
        <SectionHeader
          title="Bounded retention operation"
          description="Preview eligibility first. Execution is tenant-bound, batch-limited, audited, and available only to compliance.manage."
          icon={Database}
        />
        <div className="mt-5 space-y-4">
          <FilterBar>
            <label className="text-sm font-medium text-foreground">
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
          </FilterBar>
          {canManageRetention && !hasRetentionPreview && (
            <p className="text-xs text-muted-foreground">
              Run a preview for the selected dataset before execution is enabled.
            </p>
          )}
          {!canManageRetention && (
            <p className="text-xs text-muted-foreground">
              Execution controls are hidden from sessions without compliance.manage.
            </p>
          )}
          {retentionResult && (
            <div
              role="status"
              className="rounded-md border border-success/20 bg-success/10 p-4 text-sm text-foreground"
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
              className="rounded-md border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger"
            >
              {getConsoleErrorMessage(retentionMutation.error)}
            </p>
          )}
        </div>
      </DataPanel>

      {decisionMutation.error && (
        <p
          role="alert"
          className="rounded-md border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger"
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
