import { describe, expect, it } from 'vitest'
import { TransportError } from './api'
import { getConsoleErrorMessage } from './console-errors'

describe('console transport error presentation', () => {
  it('keeps authorization failures distinct from missing data', () => {
    expect(
      getConsoleErrorMessage(new TransportError({ kind: 'FORBIDDEN', status: 403 }))
    ).toContain('does not include')
    expect(
      getConsoleErrorMessage(new TransportError({ kind: 'UNAUTHENTICATED', status: 401 }))
    ).toContain('session')
  })

  it('provides actionable conflict and validation guidance', () => {
    expect(
      getConsoleErrorMessage(
        new TransportError({ kind: 'CONFLICT', status: 409, details: 'Already processed' })
      )
    ).toContain('changed')
    expect(
      getConsoleErrorMessage(new TransportError({ kind: 'VALIDATION', status: 422 }))
    ).toContain('Check the submitted values')
  })
})
