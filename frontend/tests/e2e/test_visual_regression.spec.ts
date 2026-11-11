import { test, expect } from './fixtures'
import {
  apiLogin,
  apiCreateCustomer,
  apiDeleteCustomer,
  generateTestCompanyId,
  generateTestCustomerName,
} from './test-helpers'

/**
 * 视觉回归测试
 *
 * 为全部 22 个页面创建截图基线，后续运行对比验证视觉一致性。
 *
 * 首次运行生成基线：
 *   npx playwright test test_visual_regression.spec.ts --update-snapshots --project=chromium
 *
 * 日常对比：
 *   npx playwright test test_visual_regression.spec.ts --project=chromium
 *
 * 更新基线（设计变更后）：
 *   npx playwright test test_visual_regression.spec.ts --update-snapshots --project=chromium
 */

// 截图配置：允许 10% 像素差异（容忍字体渲染差异）
const SCREENSHOT_OPTIONS = {
  fullPage: true,
  maxDiffPixelRatio: 0.1,
  // 遮罩动态数据区域：表格内容和图表 canvas
  mask: [] as string[],
  // 遮罩颜色
  maskColor: '#FFFFFF',
}

// 获取页面动态区域选择器列表，用于遮罩
function getDynamicMaskSelectors(page: import('@playwright/test').Page) {
  return [
    page.locator('.arco-table tbody'),
    page.locator('canvas'),
    page.locator('.arco-spin'),
    page.locator('.chart-container'),
  ]
}

test.describe('视觉回归测试', () => {
  // 不设 serial：各用例相互独立（A22 的侧边栏折叠点击只作用于自身 context，
  // Playwright 每个 test 都会新建 context/page，不会污染其他用例）。
  // serial 的代价是「一个用例失败 → 后续全部 SKIPPED」，把 21 个真实失败
  // 掩盖成「1 failed / 20 did not run」，失去回归信号。此处按 config 的
  // fullyParallel 并行执行，失败用例各自独立报告。

  test('A01: 登录页截图对比', async ({ page }) => {
    // 本用例需以「未登录」状态访问登录页截图；先清空 global-setup 注入的登录态，
    // 否则 goto('/login') 会被路由守卫重定向到首页。
    // 登录页根容器 min-height: 100vh，fullPage 截图会捕获整页内容高度，而 100vh
    // 在不同平台（本地 macOS vs CI Linux）因浏览器 chrome/滚动条差异计算为
    // 760 vs 720，导致 fullPage 基线跨平台不一致。改为视口截图（fullPage:false），
    // 截图高度恒为视口高度（Desktop Chrome 默认 1280x720），消除该平台差异。
    // 不用 page.setViewportSize：本文件为 serial 模式共享 context，setViewportSize
    // 会污染后续 A02+ 用例的视口重算，致其 fullPage 长截图高度异常。
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => localStorage.clear())
    await page.goto('/login', { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 })
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('login.png', {
      ...SCREENSHOT_OPTIONS,
      fullPage: false,
      mask: [page.locator('.arco-input-wrapper input')],
    })
  })

  test('A02: 首页截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    await expect(page).toHaveScreenshot('home.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A03: 客户列表截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/customers')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('customers.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A04: 客户详情截图对比', async ({ authenticatedPage: page }) => {
    // 通过 API 创建测试客户
    const token = await apiLogin()
    const customerName = generateTestCustomerName('visual')
    const companyId = generateTestCompanyId('visual')
    let customerId: number | undefined

    try {
      const result = await apiCreateCustomer(token, {
        company_id: companyId,
        name: customerName,
        email: 'visual-test@test.com',
        account_type: 'enterprise',
        industry: '互联网',
        settlement_type: 'fixed',
        settlement_cycle: 'monthly',
      })
      customerId = result.data?.id as number

      // 导航到客户详情
      await page.goto(`/customers/${customerId}`)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)
      await expect(page).toHaveScreenshot('customer-detail.png', {
        ...SCREENSHOT_OPTIONS,
        mask: getDynamicMaskSelectors(page),
      })
    } finally {
      // 清理测试数据
      if (customerId) {
        await apiDeleteCustomer(token, customerId).catch(() => {})
      }
    }
  })

  test('A05: 标签管理截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/tags')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('tags.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A06: 余额管理截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/billing/balances')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('balance.png', {
      ...SCREENSHOT_OPTIONS,
      // 余额页全部内容都由数据驱动：KPI 数值、表格行、分页条数会随并行用例造数而变化。
      // 表格行与分页已由 .arco-table tbody / .arco-pagination 遮罩覆盖，
      // 让基线只校验布局与卡片结构（新增/删除卡片、错位等仍会被检出）。
      mask: [
        ...getDynamicMaskSelectors(page),
        // 余额页已迁移到 a-table（共享 DataTable 组件）：表格行动态由 .arco-table tbody 遮罩，
        // 分页与 KPI 仍为数据驱动区域，保留显式遮罩让基线只校验布局与卡片结构。
        page.locator('.arco-pagination'),
        page.locator('.kpi-value'),
        page.locator('.kpi-trend'),
      ],
    })
  })

  test('A07: 计费规则截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/billing/pricing-rules')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('pricing-rules.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A08: 结算单截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/billing/invoices')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('invoices.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A09: 消耗分析截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/consumption')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    await expect(page).toHaveScreenshot('consumption.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A10: 回款分析截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/payment')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    await expect(page).toHaveScreenshot('payment.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A11: 健康度分析截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/health')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    await expect(page).toHaveScreenshot('health.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A12: 画像分析截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/profile')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    await expect(page).toHaveScreenshot('analytics-profile.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A13: 预测回款截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/forecast')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    await expect(page).toHaveScreenshot('forecast.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A14: 用户管理截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/users')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('users.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A15: 角色管理截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/roles')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('roles.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A16: 同步日志截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/system/sync-logs')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('sync-logs.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A17: 审计日志截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/system/audit-logs')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('audit-logs.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A18: 行业类型截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/system/industry-types')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('industry-types.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A19: 数据清空截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/system/database-management')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('database-management.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A20: 个人信息截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/profile')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('profile.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  test('A21: 重置密码截图对比', async ({ page }) => {
    await page.goto('/reset-password?token=test-token-visual', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot('reset-password.png', {
      ...SCREENSHOT_OPTIONS,
    })
  })

  test('A22: 侧边栏折叠态截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    // 点击折叠按钮
    const toggleBtn = page.locator('.toggle-btn')
    await expect(toggleBtn).toBeVisible()
    await toggleBtn.click()
    await page.waitForTimeout(500)

    await expect(page).toHaveScreenshot('sidebar-collapsed.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    })
  })

  // A23: 回归「表格固定列/吸顶表头越过全局 Header」。
  // 判定依据是真实绘制结果（elementFromPoint 命中最上层元素），
  // 不以 z-index 数值或 CSS 文本替代命中结论。
  test('A23: 操作列滚动时不得覆盖全局Header', async ({ authenticatedPage: page }, testInfo) => {
    test.setTimeout(180_000)
    const BACKUP_ROWS = 20
    const backupRecord = (id: number) => ({
      id,
      task_type: 'daily_backup',
      status: 'success',
      file_path: 'backups/layering-test.dump',
      file_size_bytes: 6900000,
      backup_date: '2026-11-09',
      retention_check_passed: null,
      deleted_count: 0,
      duration_seconds: 1,
      error_message: null,
      operator_id: null,
      operator_name: null,
      started_at: '2026-11-09 12:00:00',
      completed_at: '2026-11-09 12:00:01',
      created_at: '2026-11-09 12:00:01',
    })

    // 浏览器级 fixture：只喂列表数据，不向数据库写入任何备份任务。
    // 外部字体 CDN 可能长期悬挂并卡住截图（截图会等 document.fonts），本用例与字体无关。
    await page.route('https://cdn.jsdelivr.net/**', (route) => route.abort())
    await page.route('**/api/v1/system/backup/schedule', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: {
            task_name: 'daily_backup',
            enabled: false,
            backup_time: '02:00',
            next_run_time: null,
            updated_at: null,
          },
        }),
      })
    )
    await page.route('**/api/v1/system/backup/records*', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: {
            list: Array.from({ length: BACKUP_ROWS }, (_, index) => backupRecord(index + 1)),
            pagination: { total: BACKUP_ROWS, page: 1, page_size: BACKUP_ROWS },
          },
        }),
      })
    )

    await page.setViewportSize({ width: 1568, height: 483 })
    await page.goto('/system/backup')
    // 仅清掉列设置缓存保证默认列完整，保留登录态与其他本地配置
    await page.evaluate(() => localStorage.removeItem('backups_table_columns'))
    await page.reload()

    const table = page.locator('.backup-management .arco-table')
    await expect(table).toBeVisible()
    const actionHeader = table.locator('.arco-table-th.arco-table-col-fixed-right')
    const actionCells = table.locator('.arco-table-td.arco-table-col-fixed-right')
    await expect(actionHeader).toHaveCount(1)
    await expect(actionCells).toHaveCount(BACKUP_ROWS)
    await expect(actionCells.first()).toContainText('下载')

    // 把目标元素滚到 Header 垂直中心，等几何交叠真实成立
    const scrollTargetToHeaderCenter = async (selector: string) => {
      const scrolled = await page.evaluate((sel) => {
        const target = document.querySelector(sel) as HTMLElement | null
        const headerEl = document.querySelector('header.top') as HTMLElement | null
        if (!target || !headerEl) return false
        const headerRect = headerEl.getBoundingClientRect()
        const rect = target.getBoundingClientRect()
        const docTop = rect.top + window.scrollY
        const center = headerRect.top + headerRect.height / 2
        window.scrollTo(0, Math.max(0, docTop + rect.height / 2 - center))
        return true
      }, selector)
      expect(scrolled, `目标元素不存在: ${selector}`).toBe(true)
      await page.waitForFunction((sel) => {
        const target = document.querySelector(sel) as HTMLElement | null
        const headerEl = document.querySelector('header.top') as HTMLElement | null
        if (!target || !headerEl) return false
        const h = headerEl.getBoundingClientRect()
        const r = target.getBoundingClientRect()
        return (
          Math.min(h.bottom, r.bottom) - Math.max(h.top, r.top) > 4 &&
          Math.min(h.right, r.right) - Math.max(h.left, r.left) > 4
        )
      }, selector)
    }

    const assertTopmostHitIsHeader = async (selector: string) => {
      const result = await page.evaluate(
        (sel): { ok: boolean; hitClass: string | null; overlapW: number; overlapH: number } => {
          const target = document.querySelector(sel) as HTMLElement | null
          const headerEl = document.querySelector('header.top') as HTMLElement | null
          if (!target || !headerEl) {
            return { ok: false, hitClass: 'missing', overlapW: 0, overlapH: 0 }
          }
          const h = headerEl.getBoundingClientRect()
          const r = target.getBoundingClientRect()
          const top = Math.max(h.top, r.top)
          const bottom = Math.min(h.bottom, r.bottom)
          const left = Math.max(h.left, r.left)
          const right = Math.min(h.right, r.right)
          const overlapW = right - left
          const overlapH = bottom - top
          if (overlapW <= 0 || overlapH <= 0) {
            return { ok: false, hitClass: 'no-overlap', overlapW, overlapH }
          }
          const hit = document.elementFromPoint(left + overlapW / 2, top + overlapH / 2)
          return {
            ok: Boolean(hit && (hit === headerEl || headerEl.contains(hit))),
            hitClass: typeof hit?.className === 'string' ? hit.className : null,
            overlapW,
            overlapH,
          }
        },
        selector
      )
      expect(result.overlapW, '必须存在真实几何交叠').toBeGreaterThan(0)
      expect(result.overlapH, '必须存在真实几何交叠').toBeGreaterThan(0)
      expect(result.ok, `重叠区最上层元素应为 Header，实际命中: ${result.hitClass}`).toBe(true)
    }

    const headerSelector = '.backup-management .arco-table-th.arco-table-col-fixed-right'
    const firstCellSelector = '.backup-management .arco-table-td.arco-table-col-fixed-right'

    await scrollTargetToHeaderCenter(headerSelector)
    await assertTopmostHitIsHeader(headerSelector)

    await scrollTargetToHeaderCenter(firstCellSelector)
    await assertTopmostHitIsHeader(firstCellSelector)

    const screenshotPath = testInfo.outputPath('backup-header-overlap.png')
    await page.screenshot({ path: screenshotPath })
    await testInfo.attach('backup-header-overlap', {
      path: screenshotPath,
      contentType: 'image/png',
    })

    // 横向固定列：窄视口下左/中/右滚动，右固定列必须保持贴住表格可视右边界
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.setViewportSize({ width: 1024, height: 768 })
    await page.waitForFunction(() => {
      const tableEl = document.querySelector('.backup-management .arco-table')
      if (!tableEl) return false
      return Array.from(tableEl.querySelectorAll('*')).some((el) => {
        const style = getComputedStyle(el)
        return (
          el.scrollWidth > el.clientWidth + 1 &&
          (style.overflowX === 'auto' || style.overflowX === 'scroll')
        )
      })
    })

    const horizontalResult = await page.evaluate(
      (): {
        ok: boolean
        reason: string
        maxScroll: number
        samples: Array<{ scrollLeft: number; rightGap: number; visible: boolean }>
      } => {
        const tableEl = document.querySelector('.backup-management .arco-table')
        if (!tableEl) return { ok: false, reason: 'no table', maxScroll: 0, samples: [] }
        const scroller = Array.from(tableEl.querySelectorAll('*')).find((el) => {
          const style = getComputedStyle(el)
          return (
            el.scrollWidth > el.clientWidth + 1 &&
            (style.overflowX === 'auto' || style.overflowX === 'scroll')
          )
        }) as HTMLElement | undefined
        if (!scroller)
          return { ok: false, reason: 'no horizontal overflow', maxScroll: 0, samples: [] }
        const cell = tableEl.querySelector(
          '.arco-table-td.arco-table-col-fixed-right'
        ) as HTMLElement | null
        if (!cell) return { ok: false, reason: 'no fixed cell', maxScroll: 0, samples: [] }
        const maxScroll = scroller.scrollWidth - scroller.clientWidth
        const samples: Array<{ scrollLeft: number; rightGap: number; visible: boolean }> = []
        for (const ratio of [0, 0.5, 1]) {
          scroller.scrollLeft = maxScroll * ratio
          const containerRect = scroller.getBoundingClientRect()
          const cellRect = cell.getBoundingClientRect()
          samples.push({
            scrollLeft: scroller.scrollLeft,
            rightGap: Math.round(containerRect.right - cellRect.right),
            visible:
              cellRect.width > 0 &&
              cellRect.right <= containerRect.right + 2 &&
              cellRect.left >= containerRect.left - 2,
          })
        }
        return { ok: true, reason: '', maxScroll, samples }
      }
    )
    expect(horizontalResult.ok, `横向滚动探测失败: ${horizontalResult.reason}`).toBe(true)
    expect(horizontalResult.maxScroll, '该视口应产生横向滚动').toBeGreaterThan(50)
    const scrollPositions = horizontalResult.samples.map((sample) => sample.scrollLeft)
    expect(new Set(scrollPositions).size, '左/中/右三档应实际滚动').toBeGreaterThan(1)
    for (const sample of horizontalResult.samples) {
      expect(
        Math.abs(sample.rightGap),
        `操作列未贴住右边界: ${JSON.stringify(sample)}`
      ).toBeLessThanOrEqual(2)
      expect(sample.visible, `操作列不可见: ${JSON.stringify(sample)}`).toBe(true)
    }

    // 隔离不得压住 Teleport 到 body 的浮层：列设置对话框必须位于最上层
    await page.setViewportSize({ width: 1568, height: 483 })
    const gear = page.locator(
      '.backup-management .arco-table-th.arco-table-col-fixed-right button[title="列设置"]'
    )
    await expect(gear).toBeVisible()
    await gear.click()
    const modal = page.locator('.arco-modal').filter({ hasText: '自定义列' })
    await expect(modal).toBeVisible()
    const modalHit = await page.evaluate(() => {
      const modalEl = document.querySelector('.arco-modal') as HTMLElement | null
      if (!modalEl) return false
      const rect = modalEl.getBoundingClientRect()
      const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)
      return Boolean(hit && (hit === modalEl || modalEl.contains(hit)))
    })
    expect(modalHit, '列设置对话框应位于最上层').toBe(true)
    await modal.getByRole('button', { name: '取消' }).click()
    await expect(modal).toBeHidden()
  })
})
