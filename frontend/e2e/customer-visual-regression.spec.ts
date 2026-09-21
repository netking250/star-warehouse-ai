import { expect, test, type Page, type TestInfo } from '@playwright/test'

const customerSession = {
  user_id: 42,
  username: 'lin.customer',
  full_name: '林晓',
  is_admin: false,
  tenant_id: 'tenant-a',
  roles: ['customer'],
  scopes: ['chat.use'],
  session_id: 'ui-03-visual-session',
}

function observeRuntime(page: Page): { consoleErrors: string[]; failedResponses: string[] } {
  const consoleErrors: string[] = []
  const failedResponses: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', (response) => {
    if (response.status() >= 400) failedResponses.push(`${response.status()} ${response.url()}`)
  })
  return { consoleErrors, failedResponses }
}

async function installBrowserFixture(page: Page): Promise<void> {
  await page.addInitScript(() => {
    sessionStorage.setItem('star-warehouse-opening-seen', 'true')
    if (localStorage.getItem('star-warehouse-theme') === null) {
      localStorage.setItem('star-warehouse-theme', 'light')
    }

    class CustomerVisualWebSocket extends EventTarget {
      static readonly CONNECTING = 0
      static readonly OPEN = 1
      static readonly CLOSING = 2
      static readonly CLOSED = 3
      readonly url: string
      readyState = CustomerVisualWebSocket.CONNECTING
      onopen: ((event: Event) => void) | null = null
      onmessage: ((event: MessageEvent) => void) | null = null
      onerror: ((event: Event) => void) | null = null
      onclose: ((event: CloseEvent) => void) | null = null

      constructor(url: string | URL) {
        super()
        this.url = String(url)
        ;(
          window as unknown as { __customerVisualSocket?: CustomerVisualWebSocket }
        ).__customerVisualSocket = this
        queueMicrotask(() => {
          this.readyState = CustomerVisualWebSocket.OPEN
          this.onopen?.(new Event('open'))
        })
      }

      send(): void {}

      close(code = 1000, reason = ''): void {
        this.readyState = CustomerVisualWebSocket.CLOSED
        this.onclose?.(new CloseEvent('close', { code, reason, wasClean: true }))
      }
    }

    window.WebSocket = CustomerVisualWebSocket as unknown as typeof WebSocket
  })
}

async function installCustomerApi(page: Page): Promise<{
  getChatPrompts: () => string[]
  getFeedbackCount: () => number
}> {
  let authenticated = false
  let feedbackCount = 0
  const chatPrompts: string[] = []

  await page.route('**/api/v1/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(authenticated ? customerSession : null),
    })
  )
  await page.route('**/api/v1/browser/login', async (route) => {
    authenticated = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: {
        'Set-Cookie': 'star_warehouse_session=ui-03-cookie; HttpOnly; SameSite=Lax; Path=/',
      },
      body: JSON.stringify(customerSession),
    })
  })
  await page.route('**/api/v1/browser/csrf', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ csrf_token: 'ui-03-csrf' }),
    })
  )
  await page.route('**/api/v1/chat', async (route) => {
    const request = route.request()
    const body = request.postDataJSON() as { question: string }
    chatPrompts.push(body.question)
    const isLowConfidence = chatPrompts.length > 1
    const answer = isLowConfidence
      ? '退换货条件会根据商品状态、订单时间和具体政策判断。建议提供订单号后继续核对；涉及退款执行时，系统仍会保留人工审批边界。'
      : '已为你整理近期订单的查询方式。你可以提供具体订单号，我会在当前账户权限范围内核对订单状态与物流信息。\n\n如果暂时没有订单号，也可以先说明购买时间或商品名称。'
    const events = [
      'data: {"type":"runtime","event":"TURN_ACCEPTED","run_id":"run-ui-03"}',
      `data: ${JSON.stringify({ token: answer })}`,
      `data: ${JSON.stringify({ type: 'metadata', confidence_score: isLowConfidence ? 0.42 : 0.91 })}`,
      'data: {"type":"runtime","event":"RUN_COMPLETED","run_id":"run-ui-03"}',
      'data: [DONE]',
      '',
    ].join('\n\n')
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'Cache-Control': 'no-cache' },
      body: events,
    })
  })
  await page.route('**/api/v1/feedback', async (route) => {
    feedbackCount += 1
    await route.fulfill({ status: 204, body: '' })
  })
  await page.route('**/api/v1/logout', async (route) => {
    authenticated = false
    await route.fulfill({ status: 204, body: '' })
  })

  return { getChatPrompts: () => chatPrompts, getFeedbackCount: () => feedbackCount }
}

async function capture(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  const viewport = page.viewportSize()
  if (viewport) await page.mouse.move(viewport.width - 4, viewport.height - 4)
  await page.waitForTimeout(180)
  await page.screenshot({ path: testInfo.outputPath(name), fullPage: true })
}

async function login(page: Page): Promise<void> {
  await page.locator('#customer-username').fill('lin.customer')
  await page.locator('#customer-password').fill('password')
  await page.getByRole('button', { name: '进入星仓 AI' }).click()
  await expect(page.getByRole('heading', { name: '今天需要处理什么？' })).toBeVisible()
}

test('customer journey remains functional across premium login, chat, feedback, theme, and mobile states', async ({
  page,
}, testInfo) => {
  const runtime = observeRuntime(page)
  await installBrowserFixture(page)
  const api = await installCustomerApi(page)
  await page.setViewportSize({ width: 1440, height: 1000 })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: '登录客户服务' })).toBeVisible()
  await expect(page.getByText('7×24')).toHaveCount(0)
  await expect(page.getByText('企业级加密传输')).toHaveCount(0)
  await capture(page, testInfo, 'login-light.png')

  await page.getByRole('button', { name: 'Switch to dark theme' }).click()
  await capture(page, testInfo, 'login-dark.png')
  await page.getByRole('button', { name: 'Switch to light theme' }).click()
  await login(page)

  await expect(page.getByText('林晓')).toBeVisible()
  await expect(page.getByText('lin.customer')).toBeVisible()
  await expect(page.getByText('智能服务已连接')).toBeVisible()
  await expect(page.getByRole('button', { name: '帮助中心' })).toHaveCount(0)
  await capture(page, testInfo, 'empty-light.png')

  await page
    .getByRole('button', { name: /查询我的订单/ })
    .last()
    .click()
  await expect(page.getByText(/已为你整理近期订单的查询方式/)).toBeVisible()
  await expect.poll(() => api.getChatPrompts()).toContain('帮我查询一下最近的订单状态')
  await capture(page, testInfo, 'active-conversation-light.png')
  await capture(page, testInfo, 'long-answer-light.png')

  await page.getByRole('button', { name: '点赞' }).click()
  await page.getByRole('button', { name: '提交反馈' }).click()
  await expect.poll(() => api.getFeedbackCount()).toBe(1)

  await page.getByTestId('new-conversation-button').click()
  await expect(page.getByRole('heading', { name: '今天需要处理什么？' })).toBeVisible()
  await page.getByRole('textbox', { name: '消息输入' }).fill('退换货政策是什么？')
  await page.getByRole('textbox', { name: '消息输入' }).press('Enter')
  await expect(page.getByText('此回复置信度较低，可帮助我们改进。')).toBeVisible()
  await page.getByRole('button', { name: '点踩' }).click()
  await expect(page.getByText('希望我们改进什么？（可选）')).toBeVisible()
  await capture(page, testInfo, 'feedback-expanded-light.png')

  await page.getByRole('button', { name: 'Switch to dark theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await capture(page, testInfo, 'active-conversation-dark.png')
  await capture(page, testInfo, 'long-answer-dark.png')
  await capture(page, testInfo, 'feedback-expanded-dark.png')

  await page.evaluate(() => {
    const socket = (
      window as unknown as {
        __customerVisualSocket?: { onmessage: ((event: MessageEvent) => void) | null }
      }
    ).__customerVisualSocket
    socket?.onmessage?.(
      new MessageEvent('message', {
        data: JSON.stringify({
          type: 'status_change',
          payload: { title: '服务进度更新', message: '售后申请已进入人工审核。' },
        }),
      })
    )
    socket?.onmessage?.(
      new MessageEvent('message', {
        data: JSON.stringify({
          type: 'status_change',
          payload: { title: '订单状态更新', message: '订单信息已完成同步。' },
        }),
      })
    )
  })
  await expect(page.getByText('售后申请已进入人工审核。')).toBeVisible()
  await expect(page.getByText('订单信息已完成同步。')).toBeVisible()
  await page.getByRole('button', { name: '关闭通知' }).first().click()
  await expect(page.getByText('售后申请已进入人工审核。')).toHaveCount(0)

  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByTestId('opening-experience')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '今天需要处理什么？' })).toBeVisible()

  await page.setViewportSize({ width: 1280, height: 900 })
  await capture(page, testInfo, 'empty-1280-dark.png')
  await page.setViewportSize({ width: 1024, height: 850 })
  await capture(page, testInfo, 'empty-1024-dark.png')

  await page.setViewportSize({ width: 390, height: 844 })
  await capture(page, testInfo, 'mobile-chat-dark.png')
  await page.getByRole('button', { name: '打开菜单' }).click()
  await expect(page.getByLabel('客户服务导航')).toBeVisible()
  await capture(page, testInfo, 'mobile-sidebar-dark.png')
  await page.getByRole('button', { name: '关闭菜单' }).last().click()
  await page.getByRole('textbox', { name: '消息输入' }).fill('查询订单')
  await page.getByRole('textbox', { name: '消息输入' }).press('Enter')
  await expect(page.getByText(/退换货条件会根据商品状态|已为你整理近期订单/)).toBeVisible()
  await capture(page, testInfo, 'mobile-active-conversation-dark.png')

  await page.getByRole('button', { name: '点踩' }).click()
  await capture(page, testInfo, 'mobile-feedback-composer-dark.png')

  const bodyOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  expect(bodyOverflow).toBe(false)
  await page.getByTestId('logout-button').click()
  await expect(page.getByRole('heading', { name: '登录客户服务' })).toBeVisible()
  expect(runtime.consoleErrors).toEqual([])
  expect(runtime.failedResponses).toEqual([])
})

test('customer initialization presents a lightweight session-restoration state', async ({
  page,
}) => {
  await installBrowserFixture(page)
  let releaseSession: (() => void) | undefined
  const sessionGate = new Promise<void>((resolve) => {
    releaseSession = resolve
  })
  await page.route('**/api/v1/me', async (route) => {
    await sessionGate
    await route.fulfill({ status: 200, contentType: 'application/json', body: 'null' })
  })

  const navigation = page.goto('/')
  await expect(page.getByText('正在恢复会话')).toBeVisible()
  await expect(page.getByText('正在确认登录状态…')).toBeVisible()
  releaseSession?.()
  await navigation
  await expect(page.getByRole('heading', { name: '登录客户服务' })).toBeVisible()
})

test('customer login and empty workspace remain balanced at 390 and 360 pixels', async ({
  page,
}, testInfo) => {
  const runtime = observeRuntime(page)
  await installBrowserFixture(page)
  await installCustomerApi(page)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await capture(page, testInfo, 'mobile-login-390-light.png')
  await login(page)
  await capture(page, testInfo, 'mobile-empty-390-light.png')

  await page.setViewportSize({ width: 360, height: 800 })
  await capture(page, testInfo, 'mobile-empty-360-light.png')
  const bodyOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  expect(bodyOverflow).toBe(false)
  expect(runtime.consoleErrors).toEqual([])
  expect(runtime.failedResponses).toEqual([])
})
