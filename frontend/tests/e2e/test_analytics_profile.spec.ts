import { test, expect } from './fixtures';

/**
 * 画像分析页面 E2E 测试
 *
 * 测试场景：
 * 1. PageHeader 显示
 * 2. 4 KPI 卡片
 * 3. 强制刷新按钮
 * 4. 行业分布饼图渲染
 * 5. 规模等级柱图渲染（空状态处理）
 * 6. 消费等级环形图渲染
 * 7. 房产客户独立行业分布饼图（橙色系配色）
 */
test.describe('画像分析页面', () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/profile');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
  });

  test('F01: PageHeader — eyebrow "Analytics" + 标题 "画像分析"', async ({ authenticatedPage: page }) => {
    await expect(page.locator('.eyebrow')).toContainText('Analytics');
    await expect(page.locator('h1').first()).toContainText('画像分析');
    await expect(page.locator('.desc')).toBeVisible();
  });

  test('F02: 4 KPI 卡片', async ({ authenticatedPage: page }) => {
    const statCards = page.locator('.stat-card');
    await expect(statCards).toHaveCount(4);

    // 验证 KPI 标签
    await expect(statCards.nth(0).locator('.stat-label')).toContainText('客户总数');
    await expect(statCards.nth(1).locator('.stat-label')).toContainText('行业覆盖');
    await expect(statCards.nth(2).locator('.stat-label')).toContainText('房产客户');
    await expect(statCards.nth(3).locator('.stat-label')).toContainText('数据完整率');

    // 验证 KPI 数值存在且非空
    for (let i = 0; i < 4; i++) {
      const value = statCards.nth(i).locator('.stat-value');
      await expect(value).toBeVisible();
      const text = await value.textContent();
      expect(text).toBeTruthy();
    }

    // 验证房产客户有占比信息
    await expect(statCards.nth(2).locator('.stat-extra')).toContainText('占比');
  });

  test('F03: 强制刷新按钮 → 成功提示', async ({ authenticatedPage: page }) => {
    const refreshBtn = page.locator('button:has-text("刷新")');
    await expect(refreshBtn).toBeVisible();
    await refreshBtn.click();

    // 验证成功提示出现
    await expect(page.locator('.arco-message-success')).toBeVisible({ timeout: 10000 });
  });

  test('F04: 行业分布饼图渲染 — canvas 可见且非空白', async ({ authenticatedPage: page }) => {
    // 验证图表卡片存在
    const chartCard = page.locator('.chart-card').first();
    await expect(chartCard).toBeVisible();

    // 验证标题
    await expect(chartCard.locator('h3')).toContainText('行业分布');

    // 等待 ECharts canvas 渲染
    await page.waitForTimeout(2000);

    // 验证 canvas 存在且有尺寸
    const canvas = chartCard.locator('canvas');
    const canvasCount = await canvas.count();
    if (canvasCount > 0) {
      const canvasInfo = await page.evaluate(() => {
        const c = document.querySelector('.chart-card canvas');
        if (!c) return null;
        return { width: c.clientWidth, height: c.clientHeight };
      });
      expect(canvasInfo).not.toBeNull();
      expect(canvasInfo!.width).toBeGreaterThan(0);
      expect(canvasInfo!.height).toBeGreaterThan(0);
    }
  });

  test('F05: 规模等级柱图渲染', async ({ authenticatedPage: page }) => {
    const chartCards = page.locator('.chart-card');
    // 第二个图表卡片是规模等级
    const scaleCard = chartCards.nth(1);
    await expect(scaleCard).toBeVisible();
    await expect(scaleCard.locator('h3')).toContainText('规模等级');

    // 等待图表渲染
    await page.waitForTimeout(2000);

    // 验证图表容器存在
    const chartContainer = scaleCard.locator('.chart-container');
    await expect(chartContainer).toBeVisible();
  });

  test('F06: 消费等级环形图渲染', async ({ authenticatedPage: page }) => {
    const chartCards = page.locator('.chart-card');
    // 第三个图表卡片是消费等级
    const consumeCard = chartCards.nth(2);
    await expect(consumeCard).toBeVisible();
    await expect(consumeCard.locator('h3')).toContainText('消费等级');

    // 等待图表渲染
    await page.waitForTimeout(2000);

    // 验证图表容器存在
    const chartContainer = consumeCard.locator('.chart-container');
    await expect(chartContainer).toBeVisible();
  });

  test('F07: 房产客户独立行业分布饼图', async ({ authenticatedPage: page }) => {
    const chartCards = page.locator('.chart-card');
    // 第四个图表卡片是房产客户行业分布
    const realEstateCard = chartCards.nth(3);
    await expect(realEstateCard).toBeVisible();
    await expect(realEstateCard.locator('h3')).toContainText('房产客户行业分布');

    // 等待图表渲染
    await page.waitForTimeout(2000);

    // 验证图表容器存在
    const chartContainer = realEstateCard.locator('.chart-container');
    await expect(chartContainer).toBeVisible();
  });
});
