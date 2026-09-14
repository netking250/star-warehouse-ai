import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { clearLegacyBrowserCredentials, useAuthStore } from './auth'

describe('browser auth state', () => {
  it('keeps only server-derived user state in memory', () => {
    localStorage.setItem('auth-storage', '{"state":{"token":"legacy-jwt"}}')
    sessionStorage.setItem('auth-storage', 'legacy-jwt')
    localStorage.setItem('theme', 'dark')

    clearLegacyBrowserCredentials()

    const state = useAuthStore.getState()
    expect(state).not.toHaveProperty('token')
    expect(localStorage.getItem('auth-storage')).toBeNull()
    expect(sessionStorage.getItem('auth-storage')).toBeNull()
    expect(localStorage.getItem('theme')).toBe('dark')
    localStorage.removeItem('theme')
  })

  it('guards against browser credential persistence and cookie reads', () => {
    const storeSource = readFileSync(resolve(process.cwd(), 'src/stores/auth.ts'), 'utf8')
    const apiSource = readFileSync(resolve(process.cwd(), 'src/lib/api.ts'), 'utf8')
    expect(storeSource).not.toMatch(/persist\s*\(/)
    expect(`${storeSource}\n${apiSource}`).not.toMatch(
      /(?:localStorage|sessionStorage)\.(?:getItem|setItem)|document\.cookie/
    )
  })
})
