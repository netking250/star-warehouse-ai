import { expect, test } from '@playwright/test'

test('admin login uses the browser session endpoint', async ({ page }) => {
  await page.route('**/api/v1/me', async (route) => {
    await route.fulfill({ status: 401, contentType: 'application/json', body: '{}' })
  })
  await page.route('**/api/v1/browser/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: {
        'Set-Cookie': 'star_warehouse_session=admin-e2e-session; HttpOnly; SameSite=Lax; Path=/',
      },
      body: JSON.stringify({
        user_id: 2,
        username: 'adminuser',
        full_name: 'Admin User',
        is_admin: true,
        tenant_id: 'default',
        roles: ['super_admin'],
        scopes: ['operations.read'],
        session_id: 'admin-e2e-session',
      }),
    })
  })
  await page.route('**/api/v1/admin/tasks?*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.route('**/api/v1/admin/tasks-all', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ risk_tasks: 0, confidence_tasks: 0, manual_tasks: 0, total: 0 }),
    })
  })
  await page.route('**/api/v1/admin/notifications', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ notifications: [] }),
    })
  })

  await page.goto('/admin.html#/login')
  await page.locator('#admin-username').fill('adminuser')
  await page.locator('#admin-password').fill('password')
  await page.locator('form button[type="submit"]').click()
  await page.waitForURL('/admin.html#/')
  await expect(page.getByTestId('logout-button')).toBeVisible()
  expect((await page.context().cookies()).some((cookie) => cookie.httpOnly)).toBe(true)
})
