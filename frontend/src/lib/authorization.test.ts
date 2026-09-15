import { describe, expect, it } from 'vitest'
import { hasAllCapabilities, hasAnyCapability, hasCapability } from './authorization'

const analyst = {
  user_id: 7,
  username: 'analyst',
  role: 'ADMIN' as const,
  scopes: ['operations.read', 'conversations.read'],
}

describe('console capability helpers', () => {
  it('uses server-derived scopes rather than the presentation role', () => {
    expect(hasCapability(analyst, 'operations.read')).toBe(true)
    expect(hasCapability(analyst, 'operations.manage')).toBe(false)
    expect(hasCapability({ ...analyst, scopes: [] }, 'operations.read')).toBe(false)
  })

  it('supports wildcard server authority and grouped checks', () => {
    const superAdmin = { ...analyst, scopes: ['*'] }
    expect(hasAnyCapability(analyst, ['identity.read', 'conversations.read'])).toBe(true)
    expect(hasAllCapabilities(analyst, ['operations.read', 'conversations.read'])).toBe(true)
    expect(hasAllCapabilities(analyst, ['operations.read', 'identity.read'])).toBe(false)
    expect(hasCapability(superAdmin, 'compliance.manage')).toBe(true)
  })
})
