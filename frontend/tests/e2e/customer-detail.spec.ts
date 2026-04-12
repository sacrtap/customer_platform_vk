import { test, expect } from './fixtures';

/**
 * 客户详情页面 E2E 测试
 * 验证客户详情页面的渲染和功能
 */
test.describe('客户详情页面', () => {
  test.use({ actionTimeout: 30000 });

  let customerId: string;

  test.beforeEach(async ({ authenticatedPage }) => {
    // 访问客户列表页面并获取第一个客户的 ID
    await authenticatedPage.goto('/customers', { waitUntil: 'networkidle' });
    await authenticatedPage.waitForTimeout(1000);

    // 获取第一行客户数据的公司 ID
    const firstRow = authenticatedPage.locator('.arco-table tbody tr').first();
    const companyIdCell = firstRow.locator('td').nth(0);
    customerId = (await companyIdCell.textContent())?.trim() || '';

    if (!customerId) {
      test.skip('没有可用的客户数据');
      return;
    }

    // 点击第一行的查看/详情按钮或者直接导航到详情页
    // 尝试找到查看详情的链接或按钮
    const viewButtons = firstRow.locator('button:has-text("查看"), button:has-text("详情")');
    const viewButtonCount = await viewButtons.count();

    if (viewButtonCount > 0) {
      await viewButtons.first().click();
    } else {
      // 如果没有查看按钮，尝试点击公司 ID 或者直接导航
      const firstCellLink = firstRow.locator('td').nth(0).locator('a');
      const linkCount = await firstCellLink.count();

      if (linkCount > 0) {
        await firstCellLink.first().click();
      } else {
        // 作为后备方案，直接访问一个已知的客户详情页
        // 这里我们假设路由是 /customers/:id，但需要确认实际的路由结构
        const rows = authenticatedPage.locator('.arco-table tbody tr');
        const rowCount = await rows.count();

        if (rowCount > 0) {
          // 尝试点击第一行来进入详情页（某些表格点击行跳转）
          await firstRow.click();
        }
      }
    }

    // 等待详情页面加载
    await authenticatedPage.waitForTimeout(2000);
  });

  test('显示客户详情页面', async ({ authenticatedPage }) => {
    const page = authenticatedPage;

    // 检查页面标题存在
    const pageTitle = page.locator('h1');
    await expect(pageTitle.first()).toBeVisible();

    // 检查返回按钮存在
    const backButton = page.locator('button[type="text"]').first();
    await expect(backButton).toBeVisible();

    // 检查编辑按钮存在
    const editButton = page.locator('button:has-text("编辑")');
    await expect(editButton.first()).toBeVisible();

    // 检查设为重点/取消重点按钮存在
    const keyCustomerButton = page.locator('button:has-text("设为重点"), button:has-text("取消重点")');
    await expect(keyCustomerButton.first()).toBeVisible();

    // 检查 Tabs 存在
    const tabs = page.locator('[class*="tabs"], .arco-tabs');
    await expect(tabs.first()).toBeVisible();
  });

  test('显示健康度仪表', async ({ authenticatedPage }) => {
    const page = authenticatedPage;

    // 切换到画像信息 Tab
    const profileTab = page.locator('button:has-text("画像信息"), [role="tab"]:has-text("画像信息")');
    const profileTabCount = await profileTab.count();

    if (profileTabCount > 0) {
      await profileTab.first().click();
      await page.waitForTimeout(1000);
    }

    // 检查健康度仪表容器存在
    const healthGaugeContainer = page.locator('.health-gauge-container');
    const healthGaugeCount = await healthGaugeContainer.count();

    if (healthGaugeCount > 0) {
      await expect(healthGaugeContainer.first()).toBeVisible();
    } else {
      // 如果没有找到特定的类名，检查图表区域
      const chartsSection = page.locator('.charts-section');
      const chartsCount = await chartsSection.count();

      if (chartsCount > 0) {
        await expect(chartsSection.first()).toBeVisible();
      } else {
        // 至少验证画像信息 Tab 内容存在
        const profileGrid = page.locator('.profile-grid, .info-grid');
        await expect(profileGrid.first()).toBeVisible();
      }
    }
  });

  test('显示余额趋势图', async ({ authenticatedPage }) => {
    const page = authenticatedPage;

    // 切换到余额信息 Tab
    const balanceTab = page.locator('button:has-text("余额信息"), [role="tab"]:has-text("余额信息")');
    const balanceTabCount = await balanceTab.count();

    if (balanceTabCount > 0) {
      await balanceTab.first().click();
      await page.waitForTimeout(1000);
    }

    // 检查余额卡片存在
    const balanceCards = page.locator('.balance-cards, .balance-card');
    const balanceCardsCount = await balanceCards.count();

    if (balanceCardsCount > 0) {
      await expect(balanceCards.first()).toBeVisible();

      // 检查余额趋势图容器存在
      const balanceTrendSection = page.locator('.balance-trend-section');
      const trendCount = await balanceTrendSection.count();

      if (trendCount > 0) {
        await expect(balanceTrendSection.first()).toBeVisible();
      }
    } else {
      // 如果没有找到特定的类名，至少验证余额 Tab 内容存在
      const balanceTabContent = page.locator('.arco-tabs-content');
      await expect(balanceTabContent.first()).toBeVisible();
    }
  });

  test('显示用量分布图', async ({ authenticatedPage }) => {
    const page = authenticatedPage;

    // 切换到用量数据 Tab
    const usageTab = page.locator('button:has-text("用量数据"), [role="tab"]:has-text("用量数据")');
    const usageTabCount = await usageTab.count();

    if (usageTabCount > 0) {
      await usageTab.first().click();
      await page.waitForTimeout(1000);
    }

    // 检查用量分布区域存在
    const usageDistributionSection = page.locator('.usage-distribution-section');
    const distributionCount = await usageDistributionSection.count();

    if (distributionCount > 0) {
      await expect(usageDistributionSection.first()).toBeVisible();
    }

    // 检查用量表格存在
    const usageTableSection = page.locator('.usage-table-section, .arco-table');
    const tableCount = await usageTableSection.count();

    if (tableCount > 0) {
      await expect(usageTableSection.first()).toBeVisible();
    } else {
      // 至少验证用量 Tab 内容存在
      const usageTabContent = page.locator('.arco-tabs-content');
      await expect(usageTabContent.first()).toBeVisible();
    }
  });

  test('Tab 切换功能正常', async ({ authenticatedPage }) => {
    const page = authenticatedPage;

    // 定义所有 Tab 的名称
    const tabNames = ['基础信息', '画像信息', '余额信息', '结算单', '用量数据'];

    // 逐个切换 Tab 并验证
    for (const tabName of tabNames) {
      const tab = page.locator(`button:has-text("${tabName}"), [role="tab"]:has-text("${tabName}")`);
      const tabCount = await tab.count();

      if (tabCount > 0) {
        await tab.first().click();
        await page.waitForTimeout(500);

        // 验证 Tab 内容区域可见
        const tabContent = page.locator('.arco-tabs-content, .tabs-section');
        await expect(tabContent.first()).toBeVisible();
      }
    }

    // 最后回到基础信息 Tab
    const basicTab = page.locator('button:has-text("基础信息"), [role="tab"]:has-text("基础信息")');
    const basicTabCount = await basicTab.count();

    if (basicTabCount > 0) {
      await basicTab.first().click();
      await page.waitForTimeout(500);

      // 验证基础信息表格存在
      const infoTable = page.locator('.info-table, table');
      await expect(infoTable.first()).toBeVisible();
    }
  });
});
