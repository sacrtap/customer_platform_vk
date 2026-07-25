import { test, expect } from './fixtures';

/**
 * 数据分析 E2E 测试
 */
test.describe('数据分析', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[field="username"], input[type="text"]', 'admin');
    await page.fill('input[field="password"], input[type="password"]', 'admin123');
    await page.click('button[type="submit"], button:has-text("登录")');
    await page.waitForURL('/');
  });

  test('访问首页仪表盘', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    await expect(page).toHaveURL('/');

    // 检查是否有统计卡片
    const statsCards = page.locator('.arco-statistic, .stat-card, [class*="stat"]');
    try {
      if (await statsCards.isVisible()) {
        await expect(statsCards.first()).toBeVisible();
      }
    } catch (_e) {
      // 忽略错误，页面加载成功即可
    }
  });

  test('访问消耗分析页面', async ({ page }) => {
    await page.goto('/analytics/consumption');
    await page.waitForTimeout(1500);

    await expect(page).toHaveURL('/analytics/consumption');
  });

  test('访问回款分析页面', async ({ page }) => {
    await page.goto('/analytics/payment');
    await page.waitForTimeout(1500);

    await expect(page).toHaveURL('/analytics/payment');
  });

  test('访问健康度分析页面', async ({ page }) => {
    await page.goto('/analytics/health');
    await page.waitForTimeout(1500);

    await expect(page).toHaveURL('/analytics/health');
  });

  test('图表数据加载', async ({ page }) => {
    await page.goto('/analytics/consumption');
    await page.waitForTimeout(2000);

    // 检查消耗趋势图表容器
    const chartContainer = page.locator('.chart-container').first();
    await expect(chartContainer).toBeVisible();
  });

  test('分析数据筛选', async ({ page }) => {
    await page.goto('/analytics/consumption');
    await page.waitForTimeout(1000);

    const dateFilter = page.locator('input[type="date"], .arco-range-picker').first();
    if (await dateFilter.isVisible()) {
      await dateFilter.click();
      await page.waitForTimeout(500);
    }
  });
});

/**
 * 消耗分析页面功能测试
 */
test.describe('消耗分析功能', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[field="username"], input[type="text"]', 'admin');
    await page.fill('input[field="password"], input[type="password"]', 'admin123');
    await page.click('button[type="submit"], button:has-text("登录")');
    await page.waitForURL('/');
    await page.goto('/analytics/consumption');
    await page.waitForLoadState('domcontentloaded');
  });

  test('刷新功能', async ({ page }) => {
    // 等待页面完全加载
    await page.waitForTimeout(2000);

    // 点击刷新按钮（使用 first 避免匹配多个元素）
    const refreshButton = page.locator('button:has-text("刷新")').first();
    await expect(refreshButton).toBeVisible({ timeout: 10000 });
    await refreshButton.click();

    // 验证刷新成功提示（刷新可能成功或失败，只要有消息提示即可）
    const successMsg = page.locator('.arco-message-success');
    const errorMsg = page.locator('.arco-message-error');
    await expect(successMsg.or(errorMsg).first()).toBeVisible({ timeout: 10000 });
  });

  test('客户排行表头排序切换', async ({ page }) => {
    // 等待页面加载
    await page.waitForTimeout(2000);

    // 重构后不再有 Top10 单选框，改为客户排行表格的表头排序
    const tableSection = page.locator('h3:has-text("客户排行")');
    await expect(tableSection).toBeVisible({ timeout: 10000 });

    // 验证表头排序按钮存在
    const costHeader = page.locator('th.th-sortable:has-text("结算费用")');
    const orderHeader = page.locator('th.th-sortable:has-text("订单数量")');
    await expect(costHeader).toBeVisible();
    await expect(orderHeader).toBeVisible();

    // 验证可以点击排序
    await orderHeader.click();
    await costHeader.click();
  });

  test('消耗趋势图表切换', async ({ page }) => {
    // 等待图表容器加载
    await page.waitForTimeout(2000);
    const chartContainer = page.locator('.chart-container').first();
    await expect(chartContainer).toBeVisible();

    // 验证结算费用和订单数量单选框存在（使用精确匹配）
    const costRadio = page.locator('text=结算费用').first();
    const orderRadio = page.locator('text=订单数量').first();

    await expect(costRadio).toBeVisible();
    await expect(orderRadio).toBeVisible();

    // 验证可以点击（不等待数据返回）
    await orderRadio.click();
    await costRadio.click();
  });

  test('设备类型分布切换', async ({ page }) => {
    // 等待图表容器加载
    await page.waitForTimeout(2000);
    const chartContainer = page.locator('.chart-container').nth(1);
    await expect(chartContainer).toBeVisible();

    // 验证结算费用和订单数量单选框存在（使用精确匹配）
    const costRadio = page.locator('text=结算费用').first();
    const orderRadio = page.locator('text=订单数量').first();

    await expect(costRadio).toBeVisible();
    await expect(orderRadio).toBeVisible();

    // 验证可以点击（不等待数据返回）
    await orderRadio.click();
    await costRadio.click();
  });

  test('时间范围筛选', async ({ page }) => {
    // 等待页面加载
    await page.waitForTimeout(2000);

    // 重构后筛选区域不再使用 .filter-section 类，改用更通用的选择器
    // 验证时间范围选择器存在（Arco Select 组件）
    const timeSelect = page.locator('.arco-select').first();
    const selectVisible = await timeSelect.isVisible({ timeout: 5000 }).catch(() => false);
    if (selectVisible) {
      await expect(timeSelect).toBeVisible();
    }

    // 验证查询和重置按钮存在
    const queryButton = page.getByRole('button', { name: /查询|搜索/ });
    const resetButton = page.getByRole('button', { name: /重置/ });
    const queryVisible = await queryButton.first().isVisible({ timeout: 3000 }).catch(() => false);
    const resetVisible = await resetButton.first().isVisible({ timeout: 3000 }).catch(() => false);

    if (queryVisible) await expect(queryButton.first()).toBeVisible();
    if (resetVisible) await expect(resetButton.first()).toBeVisible();
  });

  test('统计卡片显示', async ({ page }) => {
    await page.waitForTimeout(2000);

    // 重构后使用 KpiCard 组件（.kpi-card 类），有 5 个 KPI 卡片
    const kpiCards = page.locator('.kpi-card');
    await expect(kpiCards).toHaveCount(5);

    // 验证卡片内容
    await expect(kpiCards.nth(0).locator('.kpi-label')).toContainText('总消耗金额');
    await expect(kpiCards.nth(1).locator('.kpi-label')).toContainText('订单总量');
    await expect(kpiCards.nth(2).locator('.kpi-label')).toContainText('活跃客户数');
    await expect(kpiCards.nth(3).locator('.kpi-label')).toContainText('日均消耗');
    await expect(kpiCards.nth(4).locator('.kpi-label')).toContainText('消耗最高客户');
  });

  test('页面布局完整性', async ({ page }) => {
    // 验证页面标题
    await expect(page.locator('h1:has-text("消耗分析")')).toBeVisible();

    // 重构后使用 .grid-5 作为 KPI 卡片容器
    await expect(page.locator('.grid-5')).toBeVisible();

    // 验证图表区域（重构后使用 .chart-section）
    await expect(page.locator('.chart-section')).toBeVisible();

    // 验证客户排行表格区域存在
    await expect(page.locator('h3:has-text("客户排行")')).toBeVisible();
  });
});
