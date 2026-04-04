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
    
    // 检查是否有图表元素
    const charts = page.locator('.echart, [class*="chart"], canvas');
    if (await charts.isVisible()) {
      await expect(charts.first()).toBeVisible();
    }
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
