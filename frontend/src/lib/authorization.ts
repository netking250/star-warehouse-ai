import type { User } from '@/types'

/** Canonical capability names returned by the server's current authorization state. */
export type Capability =
  | 'operations.read'
  | 'operations.manage'
  | 'reviews.read'
  | 'reviews.approve'
  | 'conversations.read'
  | 'identity.read'
  | 'identity.manage'
  | 'compliance.read'
  | 'compliance.manage'
  | 'exports.approve'
  | 'exports.request'
  | 'knowledge.read'
  | 'knowledge.write'
  | 'evaluation.read'
  | 'evaluation.manage'
  | 'audit.read'
  | 'refunds.approve'

/** Return true when the current server-derived session grants one capability. */
export function hasCapability(user: User | null, capability: Capability): boolean {
  const scopes = user?.scopes ?? []
  return scopes.includes('*') || scopes.includes(capability)
}

/** Return true when the current server-derived session grants any listed capability. */
export function hasAnyCapability(user: User | null, capabilities: readonly Capability[]): boolean {
  return capabilities.some((capability) => hasCapability(user, capability))
}

/** Return true when the current server-derived session grants every listed capability. */
export function hasAllCapabilities(
  user: User | null,
  capabilities: readonly Capability[]
): boolean {
  return capabilities.every((capability) => hasCapability(user, capability))
}

export const CONSOLE_OVERVIEW_CAPABILITIES = [
  'operations.read',
  'reviews.read',
  'conversations.read',
  'identity.read',
  'compliance.read',
  'evaluation.read',
] as const

export const CONSOLE_OPERATIONS_CAPABILITIES = [
  'operations.read',
  'reviews.read',
  'conversations.read',
] as const
