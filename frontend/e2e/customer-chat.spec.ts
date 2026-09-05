import { test, expect } from '@playwright/test'

test('customer login and send chat message', async ({ page }) => {
  // Mock login API
  await page.route('**/api/v1/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'test-token',
        token_type: 'bearer',
        user_id: 1,
        username: 'testuser',
        full_name: 'Test User',
        is_admin: false,
        tenant_id: 'default',
        roles: ['USER'],
        scopes: ['chat:write'],
        session_id: 'customer-e2e-session',
      }),
    })
  })

  // Mock chat API with SSE stream
  await page.route('**/api/v1/chat', async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: 'data: {"token": "您好"}\n\ndata: {"token": "！"}\n\ndata: [DONE]\n\n',
    })
  })

  // Navigate to customer entry point
  await page.goto('/')

  // Login
  await page.getByPlaceholder('请输入您的账号').fill('testuser')
  await page.getByPlaceholder('请输入您的密码').fill('password')
  await page.getByRole('button', { name: '进入星仓 AI' }).click()
  await page.waitForURL('/')

  // Assert chat page appears
  await expect(page.getByText('星仓 AI 服务助手')).toBeVisible()

  // Send chat message
  await page.getByPlaceholder('告诉星仓 AI，您需要什么帮助...').fill('你好')
  await page.getByRole('button', { name: '发送消息' }).click()

  // Assert assistant response appears
  await expect(page.getByText('您好！')).toBeVisible()
})
