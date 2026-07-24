import { test, expect } from './fixtures';
import { apiLogin, apiCreateCustomer, apiDeleteCustomer, generateTestCompanyId, generateTestCustomerName } from './test-helpers';

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
};

// 获取页面动态区域选择器列表，用于遮罩
function getDynamicMaskSelectors(page: import('@playwright/test').Page) {
  return [
    page.locator('.arco-table tbody'),
    page.locator('canvas'),
    page.locator('.arco-spin'),
    page.locator('.chart-container'),
  ];
}

test.describe('视觉回归测试', () => {
  test.describe.configure({ mode: 'serial' });

  test('A01: 登录页截图对比', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('login.png', {
      ...SCREENSHOT_OPTIONS,
      mask: [page.locator('.arco-input-wrapper input')],
    });
  });

  test('A02: 首页截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await expect(page).toHaveScreenshot('home.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A03: 客户列表截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/customers');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('customers.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A04: 客户详情截图对比', async ({ authenticatedPage: page }) => {
    // 通过 API 创建测试客户
    const token = await apiLogin();
    const customerName = generateTestCustomerName('visual');
    const companyId = generateTestCompanyId('visual');
    let customerId: number | undefined;

    try {
      const result = await apiCreateCustomer(token, {
        company_id: companyId,
        name: customerName,
        email: 'visual-test@test.com',
        account_type: 'enterprise',
        industry: '互联网',
        settlement_type: 'fixed',
        settlement_cycle: 'monthly',
      });
      customerId = result.data?.id as number;

      // 导航到客户详情
      await page.goto(`/customers/${customerId}`);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);
      await expect(page).toHaveScreenshot('customer-detail.png', {
        ...SCREENSHOT_OPTIONS,
        mask: getDynamicMaskSelectors(page),
      });
    } finally {
      // 清理测试数据
      if (customerId) {
        await apiDeleteCustomer(token, customerId).catch(() => {});
      }
    }
  });

  test('A05: 标签管理截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/tags');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('tags.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A06: 余额管理截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/billing/balances');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('balance.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A07: 计费规则截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/billing/pricing-rules');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('pricing-rules.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A08: 结算单截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/billing/invoices');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('invoices.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A09: 消耗分析截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/consumption');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await expect(page).toHaveScreenshot('consumption.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A10: 回款分析截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/payment');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await expect(page).toHaveScreenshot('payment.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A11: 健康度分析截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/health');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await expect(page).toHaveScreenshot('health.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A12: 画像分析截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/profile');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await expect(page).toHaveScreenshot('analytics-profile.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A13: 预测回款截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/analytics/forecast');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await expect(page).toHaveScreenshot('forecast.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A14: 用户管理截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/users');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('users.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A15: 角色管理截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/roles');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('roles.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A16: 同步日志截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/system/sync-logs');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('sync-logs.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A17: 审计日志截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/system/audit-logs');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('audit-logs.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A18: 行业类型截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/system/industry-types');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('industry-types.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A19: 数据清空截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/system/database-management');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('database-management.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A20: 个人信息截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/profile');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('profile.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });

  test('A21: 重置密码截图对比', async ({ page }) => {
    await page.goto('/reset-password?token=test-token-visual', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('reset-password.png', {
      ...SCREENSHOT_OPTIONS,
    });
  });

  test('A22: 侧边栏折叠态截图对比', async ({ authenticatedPage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // 点击折叠按钮
    const toggleBtn = page.locator('.toggle-btn');
    await expect(toggleBtn).toBeVisible();
    await toggleBtn.click();
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('sidebar-collapsed.png', {
      ...SCREENSHOT_OPTIONS,
      mask: getDynamicMaskSelectors(page),
    });
  });
});
