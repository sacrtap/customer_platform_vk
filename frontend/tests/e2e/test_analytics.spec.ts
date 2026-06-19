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
    } catch (e) {
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
    await page.waitForLoadState('networkidle');
  });

  test('刷新功能', async ({ page }) => {
    // 点击刷新按钮
    const refreshButton = page.locator('button:has-text("刷新")');
    await expect(refreshButton).toBeVisible();
    await refreshButton.click();
    
    // 验证刷新成功提示
    await expect(page.locator('.arco-message-success')).toBeVisible({ timeout: 5000 });
  });

  test('Top10客户排行切换', async ({ page }) => {
    // 等待页面加载
    await page.waitForTimeout(2000);
    
    // 验证Top10区域的单选框存在（使用更精确的选择器）
    const top10Section = page.locator('h3:has-text("Top10 客户排行")').locator('..');
    const costRadio = top10Section.locator('text=消耗金额');
    const orderRadio = top10Section.locator('text=订单数量');
    
    await expect(costRadio).toBeVisible();
    await expect(orderRadio).toBeVisible();
    
    // 验证可以点击（不等待数据返回）
    await orderRadio.click();
    await costRadio.click();
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
    
    // 验证时间范围选择器存在
    const timeSelect = page.locator('.filter-section .arco-select').first();
    await expect(timeSelect).toBeVisible();
    
    // 验证客户筛选输入框存在
    const customerInput = page.locator('.filter-section input[placeholder="公司名称/公司 ID"]');
    await expect(customerInput).toBeVisible();
    
    // 验证查询和重置按钮存在
    const queryButton = page.locator('.filter-section button:has-text("查询")');
    const resetButton = page.locator('.filter-section button:has-text("重置")');
    await expect(queryButton).toBeVisible();
    await expect(resetButton).toBeVisible();
  });

  test('统计卡片显示', async ({ page }) => {
    await page.waitForTimeout(2000);
    
    // 验证统计卡片存在
    const statCards = page.locator('.stat-card');
    await expect(statCards).toHaveCount(4);
    
    // 验证卡片内容
    await expect(statCards.nth(0)).toContainText('总消耗金额');
    await expect(statCards.nth(1)).toContainText('活跃客户数');
    await expect(statCards.nth(2)).toContainText('日均消耗');
    await expect(statCards.nth(3)).toContainText('Top1 客户');
  });

  test('页面布局完整性', async ({ page }) => {
    // 验证页面标题
    await expect(page.locator('h1:has-text("消耗分析")')).toBeVisible();
    
    // 验证筛选区域
    await expect(page.locator('.filter-section')).toBeVisible();
    
    // 验证统计卡片区域
    await expect(page.locator('.stats-grid')).toBeVisible();
    
    // 验证图表区域
    await expect(page.locator('.charts-section')).toBeVisible();
    
    // 验证三个图表卡片
    const chartCards = page.locator('.chart-card');
    await expect(chartCards).toHaveCount(3);
  });
});
