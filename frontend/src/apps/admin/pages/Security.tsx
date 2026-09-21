import { useState } from 'react'
import { ShieldCheck, UserRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth'
import { hasCapability } from '@/lib/authorization'
import { getConsoleErrorMessage } from '@/lib/console-errors'
import {
  useConsoleMemberships,
  useMembershipRoleMutation,
  useMembershipStatusMutation,
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
  PageHeader,
  SectionHeader,
  StatusBadge,
} from '../components/AdminPrimitives'

const BASE_ROLES = [
  'identity_manager',
  'knowledge_admin',
  'service_supervisor',
  'reviewer',
  'analyst',
  'auditor',
  'customer',
]

interface PendingSecurityAction {
  type: 'role' | 'status'
  userId: number
  username: string
  role?: string
  active?: boolean
}

export function Security(): React.ReactElement {
  const { user } = useAuthStore()
  const canRead = hasCapability(user, 'identity.read')
  const canManage = hasCapability(user, 'identity.manage')
  const canGrantSuperAdmin = user?.scopes?.includes('*') ?? false
  const memberships = useConsoleMemberships(canRead)
  const roleMutation = useMembershipRoleMutation()
  const statusMutation = useMembershipStatusMutation()
  const [pendingAction, setPendingAction] = useState<PendingSecurityAction | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  if (memberships.isLoading) return <ConsolePageSkeleton />

  const mutationError = roleMutation.error ?? statusMutation.error
  const isMutating = roleMutation.isPending || statusMutation.isPending

  const confirmAction = (): void => {
    if (!pendingAction) return
    if (pendingAction.type === 'role' && pendingAction.role) {
      roleMutation.mutate(
        { userId: pendingAction.userId, role: pendingAction.role },
        {
          onSuccess: () => {
            setSuccessMessage(`Role updated for ${pendingAction.username}.`)
            setPendingAction(null)
          },
        }
      )
    } else if (pendingAction.type === 'status' && pendingAction.active !== undefined) {
      statusMutation.mutate(
        { userId: pendingAction.userId, active: pendingAction.active },
        {
          onSuccess: () => {
            setSuccessMessage(
              `Membership ${pendingAction.active ? 'enabled' : 'disabled'} for ${pendingAction.username}.`
            )
            setPendingAction(null)
          },
        }
      )
    }
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Security & access"
        title="Tenant membership authority"
        description={`Review identity, role, and effective capability state for tenant ${user?.tenant_id ?? 'current'}. The backend remains authoritative for every action.`}
        status={<StatusBadge tone="success">Sensitive values protected</StatusBadge>}
      />

      {!canRead ? (
        <ConsoleEmptyState
          title="Membership data is not available"
          description="This page requires identity.read. Authentication is preserved; ask an authorized identity manager for access."
        />
      ) : memberships.error ? (
        <ConsoleErrorState error={memberships.error} onRetry={() => void memberships.refetch()} />
      ) : (
        <DataPanel className="p-5">
          <SectionHeader
            title="Current memberships"
            description="No passwords, tokens, session secrets, or identity-provider credentials are displayed."
            icon={ShieldCheck}
            action={<StatusBadge>{memberships.data?.length ?? 0} members</StatusBadge>}
          />
          <div className="mt-5">
            {memberships.data?.length ? (
              <DataTableShell>
                <table className={`${adminTableClassName} min-w-[760px]`}>
                  <thead>
                    <tr>
                      <th className="px-3 py-3">Identity</th>
                      <th className="px-3 py-3">Status</th>
                      <th className="px-3 py-3">Role</th>
                      <th className="px-3 py-3">Effective capabilities</th>
                      <th className="px-3 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {memberships.data.map((membership) => {
                      const isSelf = String(membership.user_id) === String(user?.user_id)
                      const roles = canGrantSuperAdmin ? ['super_admin', ...BASE_ROLES] : BASE_ROLES
                      return (
                        <tr key={membership.user_id} className="border-b last:border-0">
                          <td className="px-3 py-4">
                            <div className="flex items-center gap-3">
                              <div className="grid h-9 w-9 place-items-center rounded-md border border-border-subtle bg-muted text-muted-foreground">
                                <UserRound className="h-4 w-4" aria-hidden="true" />
                              </div>
                              <div>
                                <p className="font-medium text-foreground">{membership.username}</p>
                                <p className="text-xs text-muted-foreground">
                                  User #{membership.user_id}
                                  {isSelf ? ' · current session' : ''}
                                </p>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-4">
                            <StatusBadge tone={membership.active ? 'success' : 'neutral'}>
                              {membership.active ? 'Active' : 'Disabled'}
                            </StatusBadge>
                          </td>
                          <td className="px-3 py-4">
                            <select
                              aria-label={`Role for ${membership.username}`}
                              value={membership.role}
                              disabled={!canManage || isSelf || isMutating}
                              onChange={(event) =>
                                setPendingAction({
                                  type: 'role',
                                  userId: membership.user_id,
                                  username: membership.username,
                                  role: event.target.value,
                                })
                              }
                              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                            >
                              <option value={membership.role}>{membership.role}</option>
                              {roles
                                .filter((role) => role !== membership.role)
                                .map((role) => (
                                  <option key={role} value={role}>
                                    {role}
                                  </option>
                                ))}
                            </select>
                          </td>
                          <td className="max-w-[360px] px-3 py-4">
                            <div className="flex flex-wrap gap-1.5">
                              {membership.scopes
                                .filter((scope) => !scope.includes(':'))
                                .slice(0, 8)
                                .map((scope) => (
                                  <StatusBadge key={scope} className="font-mono text-[10px]">
                                    {scope}
                                  </StatusBadge>
                                ))}
                              {membership.scopes.filter((scope) => !scope.includes(':')).length >
                                8 && <StatusBadge>+ more</StatusBadge>}
                            </div>
                          </td>
                          <td className="px-3 py-4 text-right">
                            {canManage && !isSelf ? (
                              <Button
                                type="button"
                                variant={membership.active ? 'outline' : 'default'}
                                size="sm"
                                disabled={isMutating}
                                onClick={() =>
                                  setPendingAction({
                                    type: 'status',
                                    userId: membership.user_id,
                                    username: membership.username,
                                    active: !membership.active,
                                  })
                                }
                              >
                                {membership.active ? 'Disable' : 'Enable'}
                              </Button>
                            ) : (
                              <span className="text-xs text-muted-foreground">
                                {isSelf ? 'Self-change blocked' : 'Read only'}
                              </span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </DataTableShell>
            ) : (
              <ConsoleEmptyState
                title="No memberships found"
                description="The current tenant has no membership records returned by the authorization API."
              />
            )}
          </div>
        </DataPanel>
      )}

      {successMessage && (
        <p
          role="status"
          className="rounded-md border border-success/20 bg-success/10 px-4 py-3 text-sm text-success"
        >
          {successMessage}
        </p>
      )}
      {mutationError && (
        <p
          role="alert"
          className="rounded-md border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger"
        >
          {getConsoleErrorMessage(mutationError)}
        </p>
      )}

      <ConfirmDialog
        open={pendingAction !== null}
        title={
          pendingAction?.type === 'role'
            ? 'Change membership role?'
            : `${pendingAction?.active ? 'Enable' : 'Disable'} membership?`
        }
        description={
          pendingAction?.type === 'role'
            ? `This will assign ${pendingAction.role} to ${pendingAction.username}. The server will re-evaluate authorization and record the mutation evidence.`
            : `This will ${pendingAction?.active ? 'enable' : 'disable'} ${pendingAction?.username}'s current-tenant membership. Any access change is enforced by the backend on the next request.`
        }
        confirmLabel={
          pendingAction?.type === 'role'
            ? 'Change role'
            : pendingAction?.active
              ? 'Enable membership'
              : 'Disable membership'
        }
        destructive={pendingAction?.type === 'status' && pendingAction.active === false}
        pending={isMutating}
        onOpenChange={(open) => {
          if (!open && !isMutating) setPendingAction(null)
        }}
        onConfirm={confirmAction}
      />
    </div>
  )
}
