import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query'
import { apiFetchJson } from '@/lib/api'
import type { ConversationList, ConversationMessage, Task } from '@/types'
import type { DashboardSummary } from './useMetricsDashboard'

export interface ConsoleTaskStats {
  risk_tasks: number
  confidence_tasks: number
  manual_tasks: number
  total: number
}

export interface ConsoleAlert {
  id: number
  rule_id: number | null
  name: string
  severity: string
  status: string
  message: string
  metric_value: number | null
  threshold: number | null
  fired_at: string
  acknowledged_at: string | null
  resolved_at: string | null
}

export interface Membership {
  user_id: number
  username: string
  active: boolean
  role: string
  scopes: string[]
}

export interface Approval {
  id: string
  operation_type: string
  requester_user_id: number
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'EXECUTED'
  operation_payload_hash: string
  operation_parameters: Record<string, unknown>
  requested_at: string
  expires_at: string
  approver_user_id: number | null
  decision_at: string | null
  executed_at: string | null
}

export interface RetentionRun {
  dataset: string
  tenant_id: string
  dry_run: boolean
  eligible_count: number
  processed_count: number
  failed_count: number
  record_ids: string[]
}

export interface ConsoleReviewFilters {
  risk_level?: 'HIGH' | 'MEDIUM' | 'LOW'
}

export interface ConsoleConversationFilters {
  user_id?: string
  intent_category?: string
}

export function useConsoleSummary(enabled: boolean): UseQueryResult<DashboardSummary, Error> {
  return useQuery<DashboardSummary>({
    queryKey: ['console', 'summary'],
    enabled,
    queryFn: () => apiFetchJson<DashboardSummary>('/admin/metrics/dashboard/summary?hours=24'),
  })
}

export function useConsoleTaskStats(enabled: boolean): UseQueryResult<ConsoleTaskStats, Error> {
  return useQuery<ConsoleTaskStats>({
    queryKey: ['console', 'task-stats'],
    enabled,
    queryFn: () => apiFetchJson<ConsoleTaskStats>('/admin/tasks-all'),
  })
}

export function useActiveConsoleAlerts(enabled: boolean): UseQueryResult<ConsoleAlert[], Error> {
  return useQuery<ConsoleAlert[]>({
    queryKey: ['console', 'active-alerts'],
    enabled,
    queryFn: () => apiFetchJson<ConsoleAlert[]>('/admin/alerts/events/active'),
  })
}

export function useConsoleApprovals(enabled: boolean): UseQueryResult<Approval[], Error> {
  return useQuery<Approval[]>({
    queryKey: ['console', 'approvals'],
    enabled,
    queryFn: () => apiFetchJson<Approval[]>('/admin/compliance/approvals'),
  })
}

export function useConsoleMemberships(enabled: boolean): UseQueryResult<Membership[], Error> {
  return useQuery<Membership[]>({
    queryKey: ['console', 'memberships'],
    enabled,
    queryFn: () => apiFetchJson<Membership[]>('/admin/authorization/memberships'),
  })
}

export function useConsoleReviewTasks(
  filters: ConsoleReviewFilters,
  enabled: boolean
): UseQueryResult<Task[], Error> {
  return useQuery<Task[]>({
    queryKey: ['console', 'review-tasks', filters],
    enabled,
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters.risk_level) params.set('risk_level', filters.risk_level)
      return apiFetchJson<Task[]>(`/admin/tasks?${params.toString()}`)
    },
  })
}

export function useConsoleConversations(
  filters: ConsoleConversationFilters,
  offset: number,
  limit: number,
  enabled: boolean
): UseQueryResult<ConversationList, Error> {
  return useQuery<ConversationList>({
    queryKey: ['console', 'conversations', filters, offset, limit],
    enabled,
    queryFn: async () => {
      const params = new URLSearchParams({ offset: String(offset), limit: String(limit) })
      if (filters.user_id) params.set('user_id', filters.user_id)
      if (filters.intent_category) params.set('intent_category', filters.intent_category)
      return apiFetchJson<ConversationList>(`/admin/conversations?${params.toString()}`)
    },
  })
}

export function useConsoleConversationMessages(
  threadId: string | null,
  enabled: boolean
): UseQueryResult<ConversationMessage[], Error> {
  return useQuery<ConversationMessage[]>({
    queryKey: ['console', 'conversation', threadId],
    enabled: enabled && threadId !== null,
    queryFn: () => apiFetchJson<ConversationMessage[]>(`/admin/conversations/${threadId}`),
  })
}

export function useMembershipRoleMutation(): UseMutationResult<
  Membership,
  Error,
  { userId: number; role: string }
> {
  const queryClient = useQueryClient()
  return useMutation<Membership, Error, { userId: number; role: string }>({
    mutationFn: ({ userId, role }) =>
      apiFetchJson<Membership>(`/admin/authorization/memberships/${userId}/role`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['console', 'memberships'] })
      void queryClient.invalidateQueries({ queryKey: ['auth', 'session'] })
    },
  })
}

export function useMembershipStatusMutation(): UseMutationResult<
  Membership,
  Error,
  { userId: number; active: boolean }
> {
  const queryClient = useQueryClient()
  return useMutation<Membership, Error, { userId: number; active: boolean }>({
    mutationFn: ({ userId, active }) =>
      apiFetchJson<Membership>(`/admin/authorization/memberships/${userId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ active }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['console', 'memberships'] })
      void queryClient.invalidateQueries({ queryKey: ['auth', 'session'] })
    },
  })
}

export function useApprovalDecisionMutation(): UseMutationResult<
  Approval,
  Error,
  { approvalId: string; decision: 'APPROVE' | 'REJECT' }
> {
  const queryClient = useQueryClient()
  return useMutation<Approval, Error, { approvalId: string; decision: 'APPROVE' | 'REJECT' }>({
    mutationFn: ({ approvalId, decision }) =>
      apiFetchJson<Approval>(`/admin/compliance/approvals/${approvalId}/decision`, {
        method: 'POST',
        body: JSON.stringify({ decision }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['console', 'approvals'] })
    },
  })
}

export function useReviewDecisionMutation(): UseMutationResult<
  unknown,
  Error,
  { auditLogId: number; action: 'APPROVE' | 'REJECT' }
> {
  const queryClient = useQueryClient()
  return useMutation<unknown, Error, { auditLogId: number; action: 'APPROVE' | 'REJECT' }>({
    mutationFn: ({ auditLogId, action }) =>
      apiFetchJson(`/admin/resume/${auditLogId}`, {
        method: 'POST',
        body: JSON.stringify({ action, admin_comment: null }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['console', 'review-tasks'] })
      void queryClient.invalidateQueries({ queryKey: ['console', 'task-stats'] })
    },
  })
}

export function useRetentionMutation(): UseMutationResult<
  RetentionRun,
  Error,
  { dataset: string; mode: 'dry-run' | 'execute' }
> {
  return useMutation<RetentionRun, Error, { dataset: string; mode: 'dry-run' | 'execute' }>({
    mutationFn: ({ dataset, mode }) =>
      apiFetchJson<RetentionRun>(
        `/admin/compliance/retention/${encodeURIComponent(dataset)}/${mode}`,
        {
          method: 'POST',
          body: JSON.stringify({}),
        }
      ),
  })
}
