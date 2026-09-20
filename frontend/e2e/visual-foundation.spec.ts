import { expect, test, type Page, type TestInfo } from '@playwright/test'

const adminSession = {
  user_id: 7,
  username: 'operator',
  full_name: 'Operations Operator',
  is_admin: false,
  tenant_id: 'tenant-a',
  roles: ['analyst'],
  scopes: ['operations.read', 'reviews.read', 'conversations.read'],
  session_id: 'visual-e2e-session',
}

function observeRuntime(page: Page): { consoleErrors: string[]; failedResponses: string[] } {
  const consoleErrors: string[] = []
  const failedResponses: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', (response) => {
    if (response.status() >= 400 && !response.url().endsWith('/api/v1/me')) {
      failedResponses.push(`${response.status()} ${response.url()}`)
    }
  })
  return { consoleErrors, failedResponses }
}

async function saveScreenshot(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  await page.screenshot({ path: testInfo.outputPath(name), fullPage: true })
}

async function stubAdminReads(page: Page): Promise<void> {
  await page.route('**/api/v1/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(adminSession),
    })
  )
  await page.route('**/api/v1/admin/metrics/dashboard/summary*', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_sessions_24h: 12,
        total_sessions_7d: 96,
        avg_confidence_24h: 0.91,
        transfer_rate_24h: 0.08,
        avg_latency_ms_24h: 240,
        containment_rate_24h: 0.92,
        token_efficiency_24h: 0.4,
      }),
    })
  )
  await page.route('**/api/v1/admin/alerts/events/active', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  )
  await page.route('**/api/v1/admin/tasks-all', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ risk_tasks: 0, confidence_tasks: 0, manual_tasks: 0, total: 0 }),
    })
  )
  await page.route('**/api/v1/admin/tasks?*', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  )
  await page.route('**/api/v1/admin/conversations?*', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ threads: [], total: 0, offset: 0, limit: 20 }),
    })
  )
  await page.route('**/api/v1/admin/notifications', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ notifications: [] }),
    })
  )
}

test('customer shell renders both themes and preserves the choice without replaying opening', async ({
  page,
}, testInfo) => {
  const runtime = observeRuntime(page)
  await page.addInitScript(() => {
    if (sessionStorage.getItem('ui-01-visual-session') !== 'ready') {
      sessionStorage.clear()
      sessionStorage.setItem('ui-01-visual-session', 'ready')
      localStorage.setItem('star-warehouse-theme', 'light')
    }
  })
  await page.route('**/api/v1/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: 'null' })
  )

  await page.goto('/')
  await expect(page.getByTestId('opening-experience')).toBeVisible()
  await page.waitForTimeout(1100)
  await saveScreenshot(page, testInfo, 'opening-frame.png')
  await expect(page.getByTestId('opening-experience')).toBeHidden({ timeout: 7000 })
  await expect(page.locator('#customer-username')).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await saveScreenshot(page, testInfo, 'customer-light.png')

  await page.getByRole('button', { name: 'Switch to dark theme' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByTestId('opening-experience')).toHaveCount(0)
  await saveScreenshot(page, testInfo, 'customer-dark.png')

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.locator('#customer-username')).toBeVisible()
  await saveScreenshot(page, testInfo, 'customer-mobile-dark.png')

  expect(runtime.consoleErrors).toEqual([])
  expect(runtime.failedResponses).toEqual([])
})

test('admin shell renders both themes and keeps primary navigation operational', async ({
  page,
}, testInfo) => {
  const runtime = observeRuntime(page)
  await page.addInitScript(() => {
    if (sessionStorage.getItem('ui-01-visual-session') !== 'ready') {
      sessionStorage.clear()
      sessionStorage.setItem('ui-01-visual-session', 'ready')
      localStorage.setItem('star-warehouse-theme', 'light')
    }

    class VisualTestWebSocket extends EventTarget {
      static readonly CONNECTING = 0
      static readonly OPEN = 1
      static readonly CLOSING = 2
      static readonly CLOSED = 3
      readonly url: string
      readyState = VisualTestWebSocket.CONNECTING
      onopen: ((event: Event) => void) | null = null
      onmessage: ((event: MessageEvent) => void) | null = null
      onerror: ((event: Event) => void) | null = null
      onclose: ((event: CloseEvent) => void) | null = null

      constructor(url: string | URL) {
        super()
        this.url = String(url)
        queueMicrotask(() => {
          this.readyState = VisualTestWebSocket.OPEN
          this.onopen?.(new Event('open'))
        })
      }

      send(): void {}

      close(code = 1000, reason = ''): void {
        this.readyState = VisualTestWebSocket.CLOSED
        this.onclose?.(new CloseEvent('close', { code, reason, wasClean: true }))
      }
    }

    window.WebSocket = VisualTestWebSocket as unknown as typeof WebSocket
  })
  await stubAdminReads(page)

  await page.goto('/admin.html#/')
  await expect(page.getByTestId('opening-experience')).toBeHidden({ timeout: 7000 })
  await expect(page.getByRole('heading', { name: 'Operational overview' })).toBeVisible()
  await saveScreenshot(page, testInfo, 'admin-light.png')

  await page.getByRole('button', { name: 'Switch to dark theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await saveScreenshot(page, testInfo, 'admin-dark.png')

  await page.getByRole('link', { name: /Operations/ }).click()
  await expect(page.getByRole('heading', { name: 'Control room' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'System status' })).toBeVisible()

  expect(runtime.consoleErrors).toEqual([])
  expect(runtime.failedResponses).toEqual([])
})
