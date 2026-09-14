import { create } from 'zustand'
import type { User } from '@/types'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isInitialized: boolean
  setAuth: (user: User) => void
  clearAuth: () => void
  setInitialized: () => void
}

const LEGACY_AUTH_STORAGE_KEY = 'auth-storage'

export function clearLegacyBrowserCredentials(): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(LEGACY_AUTH_STORAGE_KEY)
  window.sessionStorage.removeItem(LEGACY_AUTH_STORAGE_KEY)
}

clearLegacyBrowserCredentials()

export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  isAuthenticated: false,
  isInitialized: false,
  setAuth: (user) => set({ user, isAuthenticated: true, isInitialized: true }),
  clearAuth: () => set({ user: null, isAuthenticated: false, isInitialized: true }),
  setInitialized: () => set({ isInitialized: true }),
}))
