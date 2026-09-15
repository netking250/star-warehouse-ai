import { expect, test, type Page } from '@playwright/test'

const baseSession = {
  user_id: 7,
  username: 'operator',
  full_name: 'Operations Operator',
  is_admin: false,
  tenant_id: 'tenant-a',
  roles: ['analyst'],
  scopes: ['operations.read', 'reviews.read', 'conversations.read'],
  session_id: 'console-e2e-session',
}

async function stubConsoleReads(page: Page, scopes = baseSession.scopes): Promise<void> {
  await page.route('**/api/v1/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ...baseSession, scopes }),
    })
  })
  await page.route('**/api/v1/admin/metrics/dashboard/summary*', async (route) => {
    await route.fulfill({
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
  })
  await page.route('**/api/v1/admin/alerts/events/active', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.route('**/api/v1/admin/tasks-all', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ risk_tasks: 0, confidence_tasks: 0, manual_tasks: 0, total: 0 }),
    })
  })
  await page.route('**/api/v1/admin/tasks?*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.route('**/api/v1/admin/conversations?*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ threads: [], total: 0, offset: 0, limit: 20 }),
    })
  })
  await page.route('**/api/v1/admin/authorization/memberships', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.route('**/api/v1/admin/compliance/approvals', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.route('**/api/v1/admin/notifications', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ notifications: [] }),
    })
  })
}

test('authorized operator opens the enterprise overview and operations workspace', async ({
  page,
}) => {
  await stubConsoleReads(page)

  await page.goto('/admin.html#/')

  await expect(page.getByRole('heading', { name: 'Operational overview' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Operations/ })).toBeVisible()
  await expect(page.getByText('12')).toBeVisible()

  await page.getByRole('link', { name: /Operations/ }).click()
  await expect(page.getByRole('heading', { name: 'Control room' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'System status' })).toBeVisible()
})

test('authenticated user without a capability is denied and does not see the menu item', async ({
  page,
}) => {
  await stubConsoleReads(page, ['operations.read'])

  await page.goto('/admin.html#/security')

  await expect(page.getByText('Access not granted')).toBeVisible()
  await expect(page.getByRole('link', { name: /Security & access/ })).toHaveCount(0)
})

test('backend 403 remains an explicit access error', async ({ page }) => {
  await stubConsoleReads(page, ['identity.read'])
  await page.unroute('**/api/v1/admin/authorization/memberships')
  await page.route('**/api/v1/admin/authorization/memberships', async (route) => {
    await route.fulfill({
      status: 403,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Membership access denied' }),
    })
  })

  await page.goto('/admin.html#/security')

  await expect(page.getByText('Your current access does not include this operation.')).toBeVisible()
})

test('approval action uses confirmation, CSRF, and refreshes current state', async ({ page }) => {
  await stubConsoleReads(page, ['compliance.read', 'exports.approve'])
  let approved = false
  const approval = {
    id: 'approval-e2e-1',
    operation_type: 'FEEDBACK_EXPORT',
    requester_user_id: 12,
    status: 'PENDING',
    operation_payload_hash: 'abcdef1234567890',
    operation_parameters: { sentiment: 'up' },
    requested_at: '2026-09-15T08:00:00Z',
    expires_at: '2026-09-15T10:00:00Z',
    approver_user_id: null,
    decision_at: null,
    executed_at: null,
  }
  await page.route('**/api/v1/admin/compliance/approvals', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ ...approval, status: approved ? 'APPROVED' : 'PENDING' }]),
    })
  })
  await page.route('**/api/v1/browser/csrf', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ csrf_token: 'console-e2e-csrf' }),
    })
  })
  await page.route(
    '**/api/v1/admin/compliance/approvals/approval-e2e-1/decision',
    async (route) => {
      approved = true
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...approval, status: 'APPROVED', approver_user_id: 7 }),
      })
    }
  )

  await page.goto('/admin.html#/compliance')
  await expect(page.getByText('FEEDBACK_EXPORT')).toBeVisible()
  await page.getByRole('button', { name: 'Approve' }).click()
  await expect(page.getByRole('heading', { name: 'Approve sensitive operation?' })).toBeVisible()
  await page.getByRole('button', { name: 'Approve operation' }).click()

  await expect(page.getByText('APPROVED')).toBeVisible()
})
