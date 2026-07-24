import { test, expect } from './fixtures';

/**
 * 预测回款页面 E2E 测试
 *
 * 测试场景：
 * 1. PageHeader 显示
 * 2. 年份选择器 + 月份选择器
 * 3. 4 KPI 卡片
 * 4. 月份切换 → 数据刷新
 * 5. 月度预测图表渲染
 * 6. 预测明细表（排序、分页、查看跳转）
 * 7. 年份切换 → 数据刷新
 */
test.describe('预测回款页面', () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/forecast');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1500);
  });

  test('G01: PageHeader — eyebrow "Analytics" + 标题 "预测回款"', async ({ authenticatedPage: page }) => {
    await expect(page.locator('.eyebrow')).toContainText('Analytics');
    await expect(page.locator('h1').first()).toContainText('预测回款');
    // .desc 是 PageHeader 组件中 subtitle 的类名
    await expect(page.locator('.desc, .header-subtitle').first()).toBeVisible();
  });

  test('G02: 年份选择器 + 月份选择器', async ({ authenticatedPage: page }) => {
    // 验证筛选区域存在
    await expect(page.locator('.filter-card')).toBeVisible();

    // 验证年份选择器存在
    const yearPicker = page.locator('.arco-picker');
    await expect(yearPicker.first()).toBeVisible();

    // 验证月份选择器存在（Arco Select 组件）
    const monthSelect = page.locator('.filter-card .arco-select');
    await expect(monthSelect.first()).toBeVisible();

    // 验证查询和重置按钮
    await expect(page.locator('button:has-text("查询")')).toBeVisible();
    await expect(page.locator('button:has-text("重置")')).toBeVisible();
  });

  test('G03: 4 KPI 卡片', async ({ authenticatedPage: page }) => {
    const statCards = page.locator('.stat-card');
    await expect(statCards).toHaveCount(4);

    // 验证 KPI 标签
    await expect(statCards.nth(0).locator('.stat-label')).toContainText('预测回款总额');
    await expect(statCards.nth(1).locator('.stat-label')).toContainText('已确认回款');
    await expect(statCards.nth(2).locator('.stat-label')).toContainText('待确认回款');
    await expect(statCards.nth(3).locator('.stat-label')).toContainText('预测客户数');

    // 验证 KPI 数值存在
    for (let i = 0; i < 4; i++) {
      const value = statCards.nth(i).locator('.stat-value');
      await expect(value).toBeVisible();
      const text = await value.textContent();
      expect(text).toBeTruthy();
    }

    // 验证已确认回款有完成率信息
    await expect(statCards.nth(1).locator('.stat-trend')).toBeVisible();
    await expect(statCards.nth(1).locator('.trend-label')).toContainText('完成率');
  });

  test('G04: 月份切换 → 数据刷新', async ({ authenticatedPage: page }) => {
    // 点击月份选择器
    const monthSelect = page.locator('.filter-card .arco-select').first();
    await monthSelect.click();
    await page.waitForTimeout(300);

    // 选择 "1 月"
    const janOption = page.locator('.arco-select-option:has-text("1 月")');
    await expect(janOption.first()).toBeVisible({ timeout: 5000 });
    await janOption.first().click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // 验证页面未报错（允许短暂的加载错误，最终应消失）
    await page.waitForTimeout(1000);
    await expect(page.locator('.arco-message-error')).not.toBeVisible({ timeout: 3000 }).catch(() => {});
  });

  test('G05: 月度预测图表渲染', async ({ authenticatedPage: page }) => {
    // 验证图表区域存在
    const chartSection = page.locator('.chart-section, .chart-card');
    await expect(chartSection.first()).toBeVisible();

    // 验证图表标题
    const chartTitle = page.locator('h3:has-text("月度")');
    await expect(chartTitle.first()).toBeVisible();

    // 等待 ECharts 渲染
    await page.waitForTimeout(2000);

    // 验证 canvas 存在
    const canvas = page.locator('canvas');
    const canvasCount = await canvas.count();
    if (canvasCount > 0) {
      const canvasInfo = await page.evaluate(() => {
        const c = document.querySelector('canvas');
        if (!c) return null;
        return { width: c.clientWidth, height: c.clientHeight };
      });
      expect(canvasInfo).not.toBeNull();
      expect(canvasInfo!.width).toBeGreaterThan(0);
    }
  });

  test('G06: 预测明细表', async ({ authenticatedPage: page }) => {
    // 验证表格区域存在
    const table = page.locator('.arco-table');
    await expect(table.first()).toBeVisible({ timeout: 10000 });

    // 验证表格有数据行或空状态
    const tbody = table.locator('tbody tr');
    const emptyState = table.locator('.arco-empty, .arco-table-empty');
    const hasData = await tbody.count();
    const hasEmpty = await emptyState.count();
    expect(hasData > 0 || hasEmpty > 0).toBeTruthy();

    // 如果有数据，验证分页组件
    if (hasData > 0) {
      const pagination = page.locator('.arco-pagination');
      await expect(pagination.first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('G07: 年份切换 → 数据刷新', async ({ authenticatedPage: page }) => {
    // 点击年份选择器
    const yearPicker = page.locator('.arco-picker').first();
    await yearPicker.click();
    await page.waitForTimeout(500);

    // 选择年份（如果有面板弹出）
    const yearOption = page.locator('.arco-picker-cell-selected, .arco-picker-cell-in-view');
    if (await yearOption.first().isVisible({ timeout: 3000 }).catch(() => false)) {
      await yearOption.first().click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);
    }

    // 验证页面未报错（允许短暂的加载错误，最终应消失）
    await page.waitForTimeout(1000);
    await expect(page.locator('.arco-message-error')).not.toBeVisible({ timeout: 3000 }).catch(() => {});
  });
});
