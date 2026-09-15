import { useCallback, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { apiFetch, clearBrowserSessionState, isTransportError, TransportError } from '@/lib/api'
import type { LoginCredentials, User } from '@/types'

interface SessionResponse {
  user_id: number
  username: string
  email?: string
  full_name: string
  is_admin: boolean
  tenant_id: string
  roles: string[]
  scopes: string[]
  session_id: string
}

interface UseAuthResult {
  user: User | null
  isAuthenticated: boolean
  isInitialized: boolean
  logout: () => Promise<void>
  login: (credentials: LoginCredentials) => Promise<SessionResponse>
  isLoading: boolean
  error: string | undefined
}

function toUser(data: SessionResponse): User {
  return {
    user_id: data.user_id,
    username: data.username,
    email: data.email,
    full_name: data.full_name,
    role: data.is_admin ? 'ADMIN' : 'USER',
    is_admin: data.is_admin,
    tenant_id: data.tenant_id,
    roles: data.roles,
    scopes: data.scopes,
    session_id: data.session_id,
  }
}

export function useAuth(): UseAuthResult {
  const { user, isAuthenticated, isInitialized, setAuth, clearAuth, setInitialized } =
    useAuthStore()
  const queryClient = useQueryClient()
  const sessionQuery = useQuery({
    queryKey: ['auth', 'session'],
    queryFn: async (): Promise<SessionResponse | null> => {
      try {
        const response = await apiFetch('/me', { method: 'GET', skip401Redirect: true })
        return response.json() as Promise<SessionResponse>
      } catch (error) {
        if (isTransportError(error) && error.kind === 'UNAUTHENTICATED') return null
        throw error
      }
    },
    retry: false,
    staleTime: 60_000,
  })

  useEffect(() => {
    if (!sessionQuery.isFetched) return
    if (sessionQuery.data) setAuth(toUser(sessionQuery.data))
    else if (sessionQuery.isSuccess) clearAuth()
    else setInitialized()
  }, [
    clearAuth,
    sessionQuery.data,
    sessionQuery.isFetched,
    sessionQuery.isSuccess,
    setAuth,
    setInitialized,
  ])

  const logout = useCallback(async (): Promise<void> => {
    try {
      await apiFetch('/logout', { method: 'POST', skip401Redirect: true })
    } catch (error) {
      // A revoked or expired session is already logged out from the server's perspective.
      if (!(isTransportError(error) && error.kind === 'UNAUTHENTICATED')) throw error
    } finally {
      clearBrowserSessionState()
      clearAuth()
      queryClient.setQueryData(['auth', 'session'], null)
    }
  }, [clearAuth, queryClient])

  const {
    mutateAsync: login,
    isPending: isLoading,
    error: mutationError,
  } = useMutation({
    mutationFn: async (credentials: LoginCredentials): Promise<SessionResponse> => {
      try {
        const response = await apiFetch('/browser/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(credentials),
          skip401Redirect: true,
          skipCsrf: true,
          retry: false,
        })
        return response.json() as Promise<SessionResponse>
      } catch (error) {
        if (isTransportError(error) && error.kind === 'UNAUTHENTICATED') {
          throw new TransportError({
            kind: error.kind,
            status: error.status,
            code: error.code,
            details: error.details,
            requestId: error.requestId,
            correlationId: error.correlationId,
            route: error.route,
            message: 'Invalid username or password',
            cause: error,
          })
        }
        throw error
      }
    },
    onSuccess: (data) => {
      clearBrowserSessionState()
      setAuth(toUser(data))
      queryClient.setQueryData(['auth', 'session'], data)
    },
  })

  return {
    user,
    isAuthenticated,
    isInitialized,
    logout,
    login,
    isLoading,
    error: mutationError ? mutationError.message : undefined,
  }
}
