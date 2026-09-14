import { useAuthStore } from '@/stores/auth'

export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const CSRF_HEADER_NAME = 'X-CSRF-Token'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE'])

let csrfToken: string | null = null
let csrfRequest: Promise<string> | null = null

export interface ApiFetchOptions extends RequestInit {
  skip401Redirect?: boolean
  skipCsrf?: boolean
}

export function getApiHeaders(contentType = true): Record<string, string> {
  return contentType ? { 'Content-Type': 'application/json' } : {}
}

export function clearBrowserSessionState(): void {
  csrfToken = null
  csrfRequest = null
}

async function loadCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken
  if (!csrfRequest) {
    csrfRequest = fetch(`${API_BASE}/browser/csrf`, {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Unable to initialize browser request protection')
        const payload = (await response.json()) as { csrf_token?: string }
        if (!payload.csrf_token) throw new Error('Browser request protection is unavailable')
        csrfToken = payload.csrf_token
        return payload.csrf_token
      })
      .finally(() => {
        csrfRequest = null
      })
  }
  return csrfRequest
}

export async function apiFetch(input: string, init?: ApiFetchOptions): Promise<Response> {
  const url = input.startsWith('http') ? input : `${API_BASE}${input}`
  const { skip401Redirect = false, skipCsrf = false, ...requestInit } = init ?? {}
  const method = (requestInit.method || 'GET').toUpperCase()
  const isFormData = requestInit.body instanceof FormData
  const headers: Record<string, string> = {
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
    ...((requestInit.headers as Record<string, string> | undefined) || {}),
  }
  if (!skipCsrf && !SAFE_METHODS.has(method)) {
    headers[CSRF_HEADER_NAME] = await loadCsrfToken()
  }
  const response = await fetch(url, {
    ...requestInit,
    method,
    credentials: 'include',
    headers,
  })
  if (response.status === 401 && !skip401Redirect) {
    clearBrowserSessionState()
    useAuthStore.getState().clearAuth()
    window.location.href = '/'
    throw new Error('Your session has expired. Please sign in again.')
  }
  return response
}
