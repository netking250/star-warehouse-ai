import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  AgentConfig,
  AgentsConfigResponse,
  AgentConfigPayload,
  AgentConfigAuditLog,
  AgentConfigVersion,
  AgentConfigVersionMetrics,
  PromptEffectReport,
  RoutingRule,
} from '@/types'
import { apiFetchJson } from '@/lib/api'

export function useAgentAuditLog(agentName: string | undefined) {
  return useQuery<AgentConfigAuditLog[]>({
    queryKey: ['admin', 'agents', 'config', agentName, 'audit-log'],
    queryFn: () =>
      apiFetchJson<AgentConfigAuditLog[]>(`/admin/agents/config/${agentName}/audit-log`),
    enabled: !!agentName,
  })
}

export function useAgentVersions(agentName: string | undefined) {
  return useQuery<AgentConfigVersion[]>({
    queryKey: ['admin', 'agents', 'config', agentName, 'versions'],
    queryFn: () => apiFetchJson<AgentConfigVersion[]>(`/admin/agents/config/${agentName}/versions`),
    enabled: !!agentName,
  })
}

export function useAgentVersionMetrics(
  agentName: string | undefined,
  versionId: number | undefined
) {
  return useQuery<AgentConfigVersionMetrics>({
    queryKey: ['admin', 'agents', 'config', agentName, 'versions', versionId, 'metrics'],
    queryFn: () =>
      apiFetchJson<AgentConfigVersionMetrics>(
        `/admin/agents/config/${agentName}/versions/${versionId}/metrics`
      ),
    enabled: !!agentName && !!versionId,
  })
}

export function useAgentReports(agentName: string | undefined) {
  return useQuery<PromptEffectReport[]>({
    queryKey: ['admin', 'agents', 'config', agentName, 'reports'],
    queryFn: () => apiFetchJson<PromptEffectReport[]>(`/admin/agents/config/${agentName}/reports`),
    enabled: !!agentName,
  })
}

export function useAgentConfig() {
  const queryClient = useQueryClient()

  const { data, isLoading, error, refetch } = useQuery<AgentsConfigResponse>({
    queryKey: ['admin', 'agents', 'config'],
    queryFn: () => apiFetchJson<AgentsConfigResponse>('/admin/agents/config'),
  })

  const updateRoutingRuleMutation = useMutation<
    RoutingRule,
    Error,
    {
      id?: number
      intent_category: string
      target_agent: string
      priority: number
      condition_json?: Record<string, unknown>
    },
    { previousData: AgentsConfigResponse | undefined }
  >({
    mutationFn: (payload) =>
      apiFetchJson<RoutingRule>(
        payload.id ? `/admin/agents/routing-rules/${payload.id}` : '/admin/agents/routing-rules',
        {
          method: payload.id ? 'PUT' : 'POST',
          body: JSON.stringify(payload),
        }
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config'] })
    },
  })

  const deleteRoutingRuleMutation = useMutation<
    { success: boolean; message: string },
    Error,
    number
  >({
    mutationFn: (id) =>
      apiFetchJson<{ success: boolean; message: string }>(`/admin/agents/routing-rules/${id}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config'] })
    },
  })

  const updateMutation = useMutation<
    AgentConfig,
    Error,
    { agentName: string; payload: AgentConfigPayload },
    { previousData: AgentsConfigResponse | undefined }
  >({
    mutationFn: ({ agentName, payload }) =>
      apiFetchJson<AgentConfig>(`/admin/agents/config/${agentName}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onMutate: async ({ agentName, payload }) => {
      await queryClient.cancelQueries({ queryKey: ['admin', 'agents', 'config'] })
      const previousData = queryClient.getQueryData<AgentsConfigResponse>([
        'admin',
        'agents',
        'config',
      ])
      queryClient.setQueryData<AgentsConfigResponse>(['admin', 'agents', 'config'], (old) => {
        if (!old) return old
        return {
          ...old,
          configs: old.configs.map((agent) =>
            agent.agent_name === agentName ? { ...agent, ...payload } : agent
          ),
        }
      })
      return { previousData }
    },
    onError: (_err, _variables, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(['admin', 'agents', 'config'], context.previousData)
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config'] })
    },
  })

  const rollbackMutation = useMutation<AgentConfig, Error, string>({
    mutationFn: (agentName) =>
      apiFetchJson<AgentConfig>(`/admin/agents/config/${agentName}/rollback`, {
        method: 'POST',
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config'] })
    },
  })

  const rollbackToVersionMutation = useMutation<
    AgentConfig,
    Error,
    { agentName: string; versionId: number }
  >({
    mutationFn: ({ agentName, versionId }) =>
      apiFetchJson<AgentConfig>(
        `/admin/agents/config/${agentName}/versions/${versionId}/rollback`,
        {
          method: 'POST',
        }
      ),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config'] })
      void queryClient.invalidateQueries({
        queryKey: ['admin', 'agents', 'config', variables.agentName, 'versions'],
      })
    },
  })

  const generateReportMutation = useMutation<
    { task_id: string; agent_name: string; report_month: string },
    Error,
    { agentName: string; reportMonth: string }
  >({
    mutationFn: ({ agentName, reportMonth }) =>
      apiFetchJson<{ task_id: string; agent_name: string; report_month: string }>(
        `/admin/agents/config/${agentName}/reports/generate`,
        {
          method: 'POST',
          body: JSON.stringify({ report_month: reportMonth }),
        }
      ),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ['admin', 'agents', 'config', variables.agentName, 'reports'],
      })
    },
  })

  return {
    agents: data?.configs ?? [],
    routingRules: data?.routing_rules ?? [],
    isLoading,
    error,
    refetch,
    mutationError:
      updateMutation.error ??
      rollbackMutation.error ??
      rollbackToVersionMutation.error ??
      updateRoutingRuleMutation.error ??
      deleteRoutingRuleMutation.error ??
      generateReportMutation.error,
    updateAgent: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,
    rollbackAgent: rollbackMutation.mutateAsync,
    isRollingBack: rollbackMutation.isPending,
    rollbackToVersion: rollbackToVersionMutation.mutateAsync,
    isRollingBackToVersion: rollbackToVersionMutation.isPending,
    generateReport: generateReportMutation.mutateAsync,
    isGeneratingReport: generateReportMutation.isPending,
    saveRoutingRule: updateRoutingRuleMutation.mutateAsync,
    isSavingRule: updateRoutingRuleMutation.isPending,
    deleteRoutingRule: deleteRoutingRuleMutation.mutateAsync,
    isDeletingRule: deleteRoutingRuleMutation.isPending,
  }
}
