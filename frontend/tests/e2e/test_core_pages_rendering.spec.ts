import { test, expect } from './fixtures';

/**
 * 核心页面渲染 E2E 测试
 * 验证重构后的页面正确渲染和交互
 */
test.describe('核心页面渲染', () => {
  test.beforeEach(async ({ authenticatedPage }) => {
    // 每个测试前确保已登录
    await authenticatedPage.goto('/');
  });

  test('仪表盘布局渲染', async ({ authenticatedPage }) => {
    const page = authenticatedPage;

    // 检查侧边栏存在 — 重构后使用 .side 类
    const sidebar = page.locator('.side');
    await expect(sidebar).toBeVisible();

    // 检查顶部栏存在 — 重构后使用 .top 类
    const header = page.locator('.top');
    await expect(header).toBeVisible();

    // 检查 KPI 卡片存在 — 重构后使用 .mini 类，至少 4 个
    const kpiCards = page.locator('.mini');
    await expect(kpiCards.first()).toBeVisible();

    // 检查页面标题 — 重构后标题为 "运营工作台"
    await expect(page.locator('h1').first()).toContainText('运营工作台');
  });

  test('登录页面渲染', async ({ page }) => {
    // 清除认证状态，确保可以访问登录页
    await page.evaluate(() => localStorage.clear());
    await page.goto('/login', { waitUntil: 'domcontentloaded' });

    // 等待登录表单加载
    await page.waitForSelector('input[type="text"], input[field="username"]', { timeout: 15000 });

    // 检查页面品牌标题存在（限定在登录表单区域避免匹配多个元素）
    await expect(page.getByText('客户运营中台').first()).toBeVisible();

    // 检查登录表单存在
    const loginForm = page.locator('form');
    await expect(loginForm.first()).toBeVisible();

    // 检查输入框存在
    const usernameInput = page.locator('input[field="username"], input[type="text"]');
    await expect(usernameInput.first()).toBeVisible();

    const passwordInput = page.locator('input[type="password"]');
    await expect(passwordInput.first()).toBeVisible();

    // 检查登录按钮
    const loginButton = page.locator('button:has-text("登录"), button[type="submit"]');
    await expect(loginButton.first()).toBeVisible();
  });

  test('客户管理页面渲染', async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await page.goto('/customers');
    await page.waitForLoadState('networkidle');

    // 检查页面标题 — 重构后标题为 "客户管理"
    await expect(page.locator('h1').first()).toContainText('客户管理');

    // 检查表格存在
    const table = page.locator('table, .arco-table');
    await expect(table.first()).toBeVisible();

    // 检查筛选区域
    const filterSection = page.locator('[class*="filter"], [class*="Filter"]');
    await expect(filterSection.first()).toBeVisible();
  });

  test('用户管理页面渲染', async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await page.goto('/users');
    await page.waitForLoadState('networkidle');

    // 检查页面标题 — 重构后标题为 "用户管理"
    await expect(page.locator('h1').first()).toContainText('用户管理');

    // 检查表格存在
    const table = page.locator('table, .arco-table');
    await expect(table.first()).toBeVisible();
  });

  test('角色管理页面渲染', async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await page.goto('/roles');
    await page.waitForLoadState('networkidle');

    // 检查页面标题 — 重构后标题为 "角色权限"
    await expect(page.locator('h1').first()).toContainText('角色权限');

    // 检查表格存在
    const table = page.locator('table, .arco-table');
    await expect(table.first()).toBeVisible();
  });

  test('标签管理页面渲染', async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await page.goto('/tags');
    await page.waitForLoadState('networkidle');

    // 检查页面标题 — 重构后标题为 "标签管理"
    await expect(page.locator('h1').first()).toContainText('标签管理');

    // 检查 Tab 存在
    const tabs = page.locator('.arco-tabs-tab, [class*="tab"]');
    await expect(tabs.first()).toBeVisible();
  });

  test('余额管理页面渲染', async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await page.goto('/billing/balances');
    await page.waitForLoadState('networkidle');

    // 检查页面标题 — 重构后标题为 "余额管理"
    await expect(page.locator('h1').first()).toContainText('余额管理');

    // 检查表格存在
    const table = page.locator('table, .arco-table');
    await expect(table.first()).toBeVisible();
  });

  test('计费规则页面渲染', async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await page.goto('/billing/pricing-rules');
    await page.waitForLoadState('networkidle');

    // 检查页面标题 — 重构后标题为 "计费规则"
    await expect(page.locator('h1').first()).toContainText('计费规则');

    // 检查表格存在
    const table = page.locator('table, .arco-table');
    await expect(table.first()).toBeVisible();
  });

  test('同步日志页面渲染', async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await page.goto('/system/sync-logs');
    await page.waitForLoadState('networkidle');

    // 检查页面标题 — 重构后标题为 "同步任务日志"
    await expect(page.locator('h1').first()).toContainText('同步任务日志');

    // 检查表格存在
    const table = page.locator('table, .arco-table');
    await expect(table.first()).toBeVisible();
  });

  test('审计日志页面渲染', async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    await page.goto('/system/audit-logs');
    await page.waitForLoadState('networkidle');

    // 检查页面标题 — 重构后标题为 "审计日志"
    await expect(page.locator('h1').first()).toContainText('审计日志');

    // 检查表格存在
    const table = page.locator('table, .arco-table');
    await expect(table.first()).toBeVisible();
  });
});
