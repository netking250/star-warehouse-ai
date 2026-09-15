import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const sourceDirectory = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function source(relativePath: string): string {
  return readFileSync(resolve(sourceDirectory, relativePath), 'utf8')
}

describe('browser transport security guard', () => {
  it('does not persist browser credentials or build browser Bearer authorization', () => {
    const productionSource = [
      source('stores/auth.ts'),
      source('lib/api.ts'),
      source('hooks/useAuth.ts'),
      source('hooks/useWebSocket.ts'),
      source('apps/customer/hooks/useChat.ts'),
    ].join('\n')

    expect(productionSource).not.toMatch(/(?:localStorage|sessionStorage)\.(?:getItem|setItem)/i)
    expect(productionSource).not.toMatch(/Authorization\s*:\s*[`'"]\s*Bearer/i)
    expect(productionSource).not.toMatch(/document\.cookie/i)
  })

  it('keeps the only direct fetch exception isolated to non-authenticated telemetry', () => {
    const apiSource = source('lib/api.ts')
    const telemetrySource = source('utils/webVitalsReporter.ts')
    expect(apiSource).toContain('fetch(')
    expect(telemetrySource).toContain('keepalive: true')
    expect(telemetrySource).not.toMatch(/Authorization|Bearer|csrf_token|access_token/i)
  })
})
