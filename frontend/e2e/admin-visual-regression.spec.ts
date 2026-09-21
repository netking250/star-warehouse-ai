import { expect, test, type Page, type TestInfo } from '@playwright/test'

const routes = [
  { path: '/', name: 'overview', heading: 'Operational overview' },
  { path: '/operations', name: 'operations', heading: 'Control room' },
  { path: '/ai', name: 'ai-runtime', heading: 'Agent orchestration' },
  { path: '/security', name: 'security', heading: 'Tenant membership authority' },
  { path: '/compliance', name: 'compliance', heading: 'Approvals and lifecycle controls' },
  { path: '/knowledge', name: 'knowledge', heading: 'Knowledge inventory' },
  { path: '/feedback', name: 'feedback', heading: 'Quality signals' },
  { path: '/metrics', name: 'metrics', heading: 'Runtime metrics' },
] as const

function installBrowserStubs(page: Page): Promise<void> {
  return page.addInitScript(() => {
    sessionStorage.setItem('star-warehouse-opening-seen', 'true')
    if (localStorage.getItem('star-warehouse-theme') === null) {
      localStorage.setItem('star-warehouse-theme', 'light')
    }

    class VisualWebSocket extends EventTarget {
      static readonly CONNECTING = 0
      static readonly OPEN = 1
      static readonly CLOSING = 2
      static readonly CLOSED = 3
      readonly url: string
      readyState = VisualWebSocket.CONNECTING
      onopen: ((event: Event) => void) | null = null
      onmessage: ((event: MessageEvent) => void) | null = null
      onerror: ((event: Event) => void) | null = null
      onclose: ((event: CloseEvent) => void) | null = null

      constructor(url: string | URL) {
        super()
        this.url = String(url)
        queueMicrotask(() => {
          this.readyState = VisualWebSocket.OPEN
          this.onopen?.(new Event('open'))
        })
      }

      send(): void {}

      close(code = 1000, reason = ''): void {
        this.readyState = VisualWebSocket.CLOSED
        this.onclose?.(new CloseEvent('close', { code, reason, wasClean: true }))
      }
    }

    window.WebSocket = VisualWebSocket as unknown as typeof WebSocket
  })
}

async function stubAdminData(page: Page): Promise<void> {
  await page.route('http://localhost:3000/**', (route) => {
    const dark = new URL(route.request().url()).searchParams.get('theme') === 'dark'
    return route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: `<style>html,body{margin:0;min-height:100%;font:14px system-ui;background:${dark ? '#111827' : '#f8fafc'};color:${dark ? '#cbd5e1' : '#475569'}}main{padding:24px}</style><main>Grafana fixture</main>`,
    })
  })
  await page.route('**/api/v1/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user_id: 7,
        username: 'operator',
        full_name: 'Operations Operator',
        is_admin: true,
        tenant_id: 'tenant-a',
        roles: ['super_admin'],
        scopes: ['*'],
        session_id: 'ui-02-visual-session',
      }),
    })
  )
  await page.route('**/api/v1/admin/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    let body: unknown = []

    if (path.endsWith('/notifications')) body = { notifications: [] }
    else if (path.endsWith('/metrics/dashboard/summary')) {
      body = {
        total_sessions_24h: 128,
        total_sessions_7d: 842,
        avg_confidence_24h: 0.91,
        transfer_rate_24h: 0.08,
        avg_latency_ms_24h: 238,
        containment_rate_24h: 0.92,
        token_efficiency_24h: 0.74,
      }
    } else if (path.endsWith('/alerts/events/active')) {
      body = [
        {
          id: 1,
          rule_id: 2,
          name: 'Review queue latency',
          severity: 'P2',
          status: 'ACTIVE',
          message: 'One review item is approaching its service target.',
          metric_value: 1,
          threshold: 5,
          fired_at: '2026-09-21T08:00:00Z',
          acknowledged_at: null,
          resolved_at: null,
        },
      ]
    } else if (path.endsWith('/tasks-all')) {
      body = { risk_tasks: 1, confidence_tasks: 2, manual_tasks: 0, total: 3 }
    } else if (path.endsWith('/tasks')) body = []
    else if (path.endsWith('/conversations')) {
      body = { threads: [], total: 0, offset: 0, limit: 20 }
    } else if (path.endsWith('/authorization/memberships')) {
      body = [
        {
          user_id: 7,
          username: 'operator',
          active: true,
          role: 'super_admin',
          scopes: ['operations.read', 'identity.read', 'compliance.read', 'knowledge.read'],
        },
        {
          user_id: 12,
          username: 'reviewer',
          active: true,
          role: 'reviewer',
          scopes: ['reviews.read', 'refunds.approve'],
        },
      ]
    } else if (path.endsWith('/compliance/approvals')) {
      body = [
        {
          id: 'approval-visual-1',
          operation_type: 'FEEDBACK_EXPORT',
          requester_user_id: 12,
          status: 'PENDING',
          operation_payload_hash: 'abcdef1234567890',
          operation_parameters: { sentiment: 'negative' },
          requested_at: '2026-09-21T08:00:00Z',
          expires_at: '2026-09-21T10:00:00Z',
          approver_user_id: null,
          decision_at: null,
          executed_at: null,
        },
      ]
    } else if (path.endsWith('/agents/config')) {
      body = {
        configs: [
          {
            agent_name: 'order_agent',
            system_prompt: 'Handle order support.',
            previous_system_prompt: null,
            confidence_threshold: 0.82,
            max_retries: 2,
            enabled: true,
            updated_at: '2026-09-21T08:00:00Z',
          },
          {
            agent_name: 'policy_agent',
            system_prompt: 'Apply policy evidence.',
            previous_system_prompt: null,
            confidence_threshold: 0.88,
            max_retries: 1,
            enabled: true,
            updated_at: '2026-09-21T08:00:00Z',
          },
        ],
        routing_rules: [
          {
            id: 1,
            intent_category: 'ORDER',
            target_agent: 'order_agent',
            priority: 10,
            condition_json: null,
            created_at: '2026-09-21T08:00:00Z',
            updated_at: '2026-09-21T08:00:00Z',
          },
        ],
      }
    } else if (path.endsWith('/knowledge')) {
      body = [
        {
          id: 1,
          filename: 'returns-policy.md',
          content_type: 'text/markdown',
          doc_size_bytes: 18432,
          sync_status: 'done',
          sync_message: 'Indexed successfully',
          last_synced_at: '2026-09-21T08:00:00Z',
          created_at: '2026-09-20T08:00:00Z',
          updated_at: '2026-09-21T08:00:00Z',
        },
      ]
    } else if (path.endsWith('/feedback/csat')) {
      body = { days: 30, trend: [{ date: '2026-09-20', avg_score: 4.4, count: 18 }] }
    } else if (path.endsWith('/feedback')) {
      body = {
        items: [
          {
            id: 1,
            user_id: 42,
            thread_id: 'thread-quality-review',
            message_index: 3,
            score: 2,
            comment: 'The answer needed clearer next steps.',
            category: 'clarity',
            agent_type: 'order_agent',
            confidence_score: 0.66,
            created_at: '2026-09-21T08:00:00Z',
          },
          {
            id: 2,
            user_id: 43,
            thread_id: 'thread-positive',
            message_index: 4,
            score: 5,
            comment: 'Resolved quickly.',
            category: 'resolution',
            agent_type: 'policy_agent',
            confidence_score: 0.93,
            created_at: '2026-09-21T08:30:00Z',
          },
        ],
        total: 2,
        offset: 0,
        limit: 20,
      }
    } else if (path.includes('/metrics/dashboard/alerts')) body = []
    else if (path.includes('/metrics/dashboard/intent-accuracy')) {
      body = [
        {
          hour: '2026-09-21T08:00:00Z',
          intent_category: 'ORDER',
          total: 48,
          correct: 44,
          accuracy: 0.916,
        },
      ]
    } else if (path.includes('/metrics/dashboard/transfer-reasons')) {
      body = [{ reason: 'policy review', count: 6, percentage: 35 }]
    } else if (path.includes('/metrics/dashboard/token-usage')) {
      body = [{ date: '2026-09-21', input_tokens: 12000, output_tokens: 4200, total_tokens: 16200 }]
    } else if (path.includes('/metrics/dashboard/latency-trend')) {
      body = [
        {
          hour: '2026-09-21T08:00:00Z',
          avg_latency_ms: 238,
          p95_latency_ms: 410,
          p99_latency_ms: 620,
        },
      ]
    } else if (path.includes('/metrics/dashboard/rag-precision')) {
      body = [{ date: '2026-09-21', avg_score: 0.89, count: 36 }]
    } else if (path.includes('/metrics/dashboard/hallucination-rate')) {
      body = [{ date: '2026-09-21', hallucination_rate: 0.02, sampled_count: 50 }]
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })
  })
}

async function capture(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  const viewport = page.viewportSize()
  if (viewport) await page.mouse.move(viewport.width - 4, viewport.height - 4)
  await page.waitForTimeout(250)
  await page.screenshot({ path: testInfo.outputPath(name), fullPage: true })
}

test('all active Admin routes share the enterprise visual system in both themes', async ({
  page,
}, testInfo) => {
  const consoleErrors: string[] = []
  const failedResponses: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', (response) => {
    if (response.status() >= 400) failedResponses.push(`${response.status()} ${response.url()}`)
  })

  await installBrowserStubs(page)
  await stubAdminData(page)
  await page.setViewportSize({ width: 1440, height: 1000 })

  for (const route of routes) {
    await page.goto(`/admin.html#${route.path}`)
    await expect(page.getByRole('heading', { name: route.heading })).toBeVisible()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
    await capture(page, testInfo, `${route.name}-light.png`)
  }

  await page.getByRole('button', { name: 'Switch to dark theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  for (const route of routes) {
    await page.goto(`/admin.html#${route.path}`)
    await expect(page.getByRole('heading', { name: route.heading })).toBeVisible()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
    await capture(page, testInfo, `${route.name}-dark.png`)
  }

  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  await page.setViewportSize({ width: 1024, height: 900 })
  for (const route of routes.filter(({ name }) =>
    ['overview', 'operations', 'knowledge'].includes(name)
  )) {
    await page.goto(`/admin.html#${route.path}`)
    await expect(page.getByRole('heading', { name: route.heading })).toBeVisible()
    await capture(page, testInfo, `${route.name}-1024-dark.png`)
  }

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/admin.html#/')
  await page.getByRole('button', { name: 'Open navigation' }).click()
  await expect(
    page.getByRole('navigation', { name: 'Enterprise console navigation' })
  ).toBeVisible()
  await page.getByRole('link', { name: /Operations/ }).click()
  await expect(page.getByRole('heading', { name: 'Control room' })).toBeVisible()
  await capture(page, testInfo, 'admin-mobile-dark.png')

  expect(consoleErrors).toEqual([])
  expect(failedResponses).toEqual([])
})
