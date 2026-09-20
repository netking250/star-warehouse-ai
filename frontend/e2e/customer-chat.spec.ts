import { expect, test } from '@playwright/test'

test('customer browser session uses HttpOnly cookie, CSRF, and server logout', async ({ page }) => {
  let authenticated = false
  let chatMutationSeen = false

  await page.route('**/api/v1/me', async (route) => {
    await route.fulfill({
      status: authenticated ? 200 : 401,
      contentType: 'application/json',
      body: authenticated
        ? JSON.stringify({
            user_id: 1,
            username: 'testuser',
            full_name: 'Test User',
            email: 'testuser@example.com',
            is_admin: false,
            tenant_id: 'default',
            roles: ['customer'],
            scopes: ['chat.use'],
            session_id: 'customer-e2e-session',
          })
        : JSON.stringify({ detail: 'Missing authentication token' }),
    })
  })
  await page.route('**/api/v1/browser/csrf', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ csrf_token: 'customer-e2e-csrf' }),
    })
  })
  await page.route('**/api/v1/browser/login', async (route) => {
    authenticated = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: {
        'Set-Cookie': 'star_warehouse_session=opaque-e2e-session; HttpOnly; SameSite=Lax; Path=/',
      },
      body: JSON.stringify({
        user_id: 1,
        username: 'testuser',
        full_name: 'Test User',
        is_admin: false,
        tenant_id: 'default',
        roles: ['customer'],
        scopes: ['chat.use'],
        session_id: 'customer-e2e-session',
      }),
    })
  })
  await page.route('**/api/v1/chat', async (route) => {
    expect(route.request().headers()['x-csrf-token']).toBe('customer-e2e-csrf')
    expect(route.request().headers().cookie).toContain('star_warehouse_session=')
    chatMutationSeen = true
    await route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
      body: 'data: {"token": "Hello"}\n\ndata: [DONE]\n\n',
    })
  })
  await page.route('**/api/v1/logout', async (route) => {
    expect(route.request().headers()['x-csrf-token']).toBe('customer-e2e-csrf')
    authenticated = false
    await route.fulfill({
      status: 204,
      headers: {
        'Set-Cookie': 'star_warehouse_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0',
      },
    })
  })

  await page.goto('/')
  await page.locator('#customer-username').fill('testuser')
  await page.locator('#customer-password').fill('password')
  await page.locator('form button[type="submit"]').click()
  await expect(page.locator('textarea')).toBeVisible()

  const authCookie = (await page.context().cookies()).find(
    (cookie) => cookie.name === 'star_warehouse_session'
  )
  expect(authCookie?.httpOnly).toBe(true)
  const browserStorage = await page.evaluate(() => ({
    local: Object.entries(localStorage),
    session: Object.entries(sessionStorage),
  }))
  expect(browserStorage.session).toEqual([['star-warehouse-opening-seen', 'true']])
  expect(browserStorage.local).toEqual([])
  expect(JSON.stringify(browserStorage)).not.toMatch(/opaque-e2e-session|customer-e2e-csrf/i)

  await page.locator('textarea').fill('hello')
  await page.locator('textarea').press('Enter')
  await expect.poll(() => chatMutationSeen).toBe(true)

  await page.getByTestId('logout-button').click()
  await page.reload()
  await expect(page.locator('#customer-username')).toBeVisible()
})
