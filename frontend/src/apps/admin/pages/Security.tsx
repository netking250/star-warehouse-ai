import { useState } from 'react'
import { ShieldCheck, UserRound } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">
          Security & access
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
          Tenant membership authority
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          Review current local membership state for tenant{' '}
          <span className="font-medium text-slate-700">{user?.tenant_id ?? 'current'}</span>.
          Capabilities are shown from the server response; the backend remains authoritative for
          every action.
        </p>
      </div>

      {!canRead ? (
        <ConsoleEmptyState
          title="Membership data is not available"
          description="This page requires identity.read. Authentication is preserved; ask an authorized identity manager for access."
        />
      ) : memberships.error ? (
        <ConsoleErrorState error={memberships.error} onRetry={() => void memberships.refetch()} />
      ) : (
        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <ShieldCheck className="h-5 w-5 text-indigo-600" aria-hidden="true" />
                Current memberships
              </CardTitle>
              <p className="mt-1 text-sm text-slate-500">
                No passwords, tokens, session secrets, or identity-provider credentials are
                displayed.
              </p>
            </div>
            <Badge variant="outline">{memberships.data?.length ?? 0} members</Badge>
          </CardHeader>
          <CardContent>
            {memberships.data?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="border-b text-xs uppercase tracking-wide text-slate-500">
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
                              <div className="grid h-9 w-9 place-items-center rounded-xl bg-slate-100 text-slate-600">
                                <UserRound className="h-4 w-4" aria-hidden="true" />
                              </div>
                              <div>
                                <p className="font-medium text-slate-800">{membership.username}</p>
                                <p className="text-xs text-slate-500">
                                  User #{membership.user_id}
                                  {isSelf ? ' · current session' : ''}
                                </p>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-4">
                            <Badge variant={membership.active ? 'secondary' : 'outline'}>
                              {membership.active ? 'Active' : 'Disabled'}
                            </Badge>
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
                                  <Badge
                                    key={scope}
                                    variant="outline"
                                    className="font-mono text-[10px]"
                                  >
                                    {scope}
                                  </Badge>
                                ))}
                              {membership.scopes.filter((scope) => !scope.includes(':')).length >
                                8 && <Badge variant="outline">+ more</Badge>}
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
                              <span className="text-xs text-slate-400">
                                {isSelf ? 'Self-change blocked' : 'Read only'}
                              </span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <ConsoleEmptyState
                title="No memberships found"
                description="The current tenant has no membership records returned by the authorization API."
              />
            )}
          </CardContent>
        </Card>
      )}

      {successMessage && (
        <p
          role="status"
          className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
        >
          {successMessage}
        </p>
      )}
      {mutationError && (
        <p
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
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
