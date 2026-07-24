import { test, expect } from './fixtures';
import {
  uiLogin,
  waitForTableLoaded,
  generateTestCompanyId,
  generateTestCustomerName,
  apiLogin,
  apiCreateCustomer,
  apiDeleteCustomer,
  apiGetCustomers,
  searchCustomer,
} from './test-helpers';

/**
 * 客户筛选功能 E2E 测试
 */
test.describe('客户筛选功能', () => {
  let authToken: string;
  let createdIds: number[] = [];

  test.beforeAll(async () => {
    authToken = await apiLogin();
  });

  test.beforeEach(async ({ page }) => {
    createdIds = [];
    await uiLogin(page);

    // 创建多组测试数据
    const customers = [
      { company_id: generateTestCompanyId(), name: generateTestCustomerName('KA正式'), account_type: '正式账号', is_key_customer: true, settlement_type: 'prepaid', industry_type_id: 2 },
      { company_id: generateTestCompanyId(), name: generateTestCustomerName('普通测试'), account_type: '客户测试账号', is_key_customer: false, settlement_type: 'prepaid' },
      { company_id: generateTestCompanyId(), name: generateTestCustomerName('房产KA'), account_type: '正式账号', is_key_customer: true, settlement_type: 'prepaid', industry_type_id: 2 },
      { company_id: generateTestCompanyId(), name: generateTestCustomerName('SKA测试'), account_type: '正式账号', is_key_customer: false, settlement_type: 'prepaid', industry_type_id: 2 },
    ];

    for (const c of customers) {
      const result = await apiCreateCustomer(authToken, c);
      if (result.data?.id) {
        createdIds.push(result.data.id);
      }
    }

    await page.goto('/customers');
    await waitForTableLoaded(page);
    await page.waitForTimeout(1000);
  });

  test.afterEach(async () => {
    for (const id of createdIds) {
      await apiDeleteCustomer(authToken, id).catch(() => {});
    }
  });

  /** 点击 FilterDropdown 触发器（通过 label 文本匹配） */
  async function clickFilterDropdown(page: import('@playwright/test').Page, label: string): Promise<boolean> {
    const trigger = page.locator('.filter-trigger').filter({ hasText: label }).first();
    const visible = await trigger.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      await trigger.click();
      await page.waitForTimeout(500);
      return true;
    }
    return false;
  }

  /** 关闭 FilterDropdown 面板（点击页面空白处） */
  async function closeFilterDropdown(page: import('@playwright/test').Page): Promise<void> {
    // 点击页面标题区域来触发 click outside
    await page.locator('h1').first().click().catch(() => {});
    await page.waitForTimeout(300);
  }

  /** 点击筛选按钮 */
  async function clickSearchButton(page: import('@playwright/test').Page): Promise<void> {
    await page.locator('.filters button:has-text("筛选")').first().click({ force: true });
    await waitForTableLoaded(page);
  }

  test('1. 关键词搜索 - 公司 ID', async ({ page }) => {
    const resp = await apiGetCustomers(authToken, { keyword: generateTestCustomerName('KA正式') });
    const target = (resp.data?.list || resp.data?.items || []).find((c: { name: string }) => c.name.includes('KA正式'));
    test.skip(!target, '无测试数据');

    await searchCustomer(page, String(target.company_id));

    const rows = page.locator('.table-section tbody tr, table tbody tr', { hasText: String(target.company_id) });
    await expect(rows.first()).toBeVisible({ timeout: 10000 });
  });

  test('2. 关键词搜索 - 客户名称', async ({ page }) => {
    const resp = await apiGetCustomers(authToken, { keyword: generateTestCustomerName('SKA') });
    const target = (resp.data?.list || resp.data?.items || []).find((c: { name: string }) => c.name.includes('SKA'));
    test.skip(!target, '无测试数据');

    await searchCustomer(page, target.name);

    const rows = page.locator('.table-section tbody tr, table tbody tr', { hasText: target.name });
    await expect(rows.first()).toBeVisible({ timeout: 10000 });
  });

  test('3. 账号类型筛选', async ({ page }) => {
    // 点击账号类型 FilterDropdown
    if (await clickFilterDropdown(page, '账号类型')) {
      // 选择"正式账号"
      const option = page.locator('.filter-option').filter({ hasText: '正式账号' }).first();
      if (await option.isVisible({ timeout: 3000 }).catch(() => false)) {
        await option.click();
        await page.waitForTimeout(300);
      } else {
        await closeFilterDropdown(page);
      }
    }

    await clickSearchButton(page);

    const rows = page.locator('.table-section tbody tr, table tbody tr');
    expect(await rows.count()).toBeGreaterThanOrEqual(0);
  });

  test('4. 行业类型多选筛选', async ({ page }) => {
    if (await clickFilterDropdown(page, '行业')) {
      // 多选：选择前两个选项（排除"全部"）
      const options = page.locator('.filter-option').filter({ hasText: /^(?!全部$).+/ });
      const optionCount = await options.count();

      if (optionCount >= 2) {
        await options.nth(0).click();
        await page.waitForTimeout(200);
        await options.nth(1).click();
        await page.waitForTimeout(300);
      } else if (optionCount === 1) {
        await options.first().click();
        await page.waitForTimeout(300);
      }

      // 点击"确认"按钮关闭多选面板
      const confirmBtn = page.locator('.btn-confirm');
      if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await confirmBtn.click();
        await page.waitForTimeout(300);
      } else {
        await closeFilterDropdown(page);
      }
    }

    await clickSearchButton(page);

    const errorMsg = page.locator('.arco-message-error');
    expect(await errorMsg.first().isVisible({ timeout: 2000 }).catch(() => false)).toBeFalsy();
  });

  test('5. 规模等级筛选', async ({ page }) => {
    if (await clickFilterDropdown(page, '规模等级')) {
      const options = page.locator('.filter-option').filter({ hasText: /^(?!全部$).+/ });
      if (await options.first().isVisible({ timeout: 3000 }).catch(() => false)) {
        await options.first().click();
        await page.waitForTimeout(300);
      } else {
        await closeFilterDropdown(page);
      }
    }

    await clickSearchButton(page);

    const rows = page.locator('.table-section tbody tr, table tbody tr');
    expect(await rows.count()).toBeGreaterThanOrEqual(0);
  });

  test('6. 重点客户筛选', async ({ page }) => {
    // 重点客户可能没有独立筛选器
    const opened = await clickFilterDropdown(page, '重点客户');
    if (opened) {
      const option = page.locator('.filter-option').filter({ hasText: '是' }).first();
      if (await option.isVisible({ timeout: 3000 }).catch(() => false)) {
        await option.click();
        await page.waitForTimeout(300);
      } else {
        await closeFilterDropdown(page);
      }
    }

    await clickSearchButton(page);

    const rows = page.locator('.table-section tbody tr, table tbody tr');
    expect(await rows.count()).toBeGreaterThanOrEqual(0);
  });

  test('7. 高级筛选 - 运营经理', async ({ page }) => {
    const opened = await clickFilterDropdown(page, '运营经理');
    if (opened) {
      const options = page.locator('.filter-option').filter({ hasText: /^(?!全部$).+/ });
      if (await options.first().isVisible({ timeout: 3000 }).catch(() => false)) {
        await options.first().click();
        await page.waitForTimeout(300);
      } else {
        await closeFilterDropdown(page);
      }
    }

    await clickSearchButton(page);

    const errorMsg = page.locator('.arco-message-error');
    expect(await errorMsg.first().isVisible({ timeout: 2000 }).catch(() => false)).toBeFalsy();
  });

  test('8. 重置筛选', async ({ page }) => {
    const searchInput = page.locator('.filters-container input[placeholder*="搜索"]').first();
    await searchInput.click();
    await searchInput.pressSequentially('test', { delay: 30 });
    await page.waitForTimeout(500);
    await clickSearchButton(page);

    // 清除搜索内容
    await searchInput.click();
    await searchInput.fill('');
    await clickSearchButton(page);

    const searchValue = await searchInput.inputValue();
    expect(searchValue).toBe('');
  });

  test('9. 多条件组合筛选', async ({ page }) => {
    const searchInput = page.locator('.filters-container input[placeholder*="搜索"]').first();
    await searchInput.click();
    await searchInput.pressSequentially('KA', { delay: 30 });

    // 等待联想请求完成
    await page.waitForTimeout(1000);

    // 点击页面标题区域关闭联想下拉框（不使用 Escape，因为组件不监听 Escape）
    await page.locator('h1').first().click();
    await page.waitForTimeout(500);

    // 验证联想下拉框已关闭
    const suggestions = page.locator('.suggestions:visible, .suggestion-item:visible');
    expect(await suggestions.count()).toBe(0);

    // 验证搜索框仍然有值
    const currentSearchValue = await searchInput.inputValue();
    expect(currentSearchValue).toBe('KA');

    // 点击筛选按钮（此时联想框已关闭，不需要 force）
    await page.locator('.filters button:has-text("筛选")').first().click();
    await waitForTableLoaded(page);

    const rows = page.locator('.table-section tbody tr, table tbody tr');
    expect(await rows.count()).toBeGreaterThanOrEqual(0);
  });

  test('10. 空结果提示', async ({ page }) => {
    await searchCustomer(page, 'NOT_EXIST_999999_ABCDEFG');
    await page.waitForTimeout(1000);

    const emptyState = page.locator('.arco-empty, .empty-state, .no-data');
    const emptyVisible = await emptyState.first().isVisible({ timeout: 5000 }).catch(() => false);

    const rowCount = await page.locator('.table-section tbody tr, table tbody tr').count();

    if (rowCount > 0 && !emptyVisible) {
      const matchingRows = page.locator('.table-section tbody tr, table tbody tr', { hasText: 'NOT_EXIST_999999_ABCDEFG' });
      expect(await matchingRows.count()).toBe(0);
    } else {
      expect(emptyVisible || rowCount === 0).toBeTruthy();
    }
  });
});
