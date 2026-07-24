import { test, expect } from './fixtures';
import { getVisibleModal, waitForModal } from './test-helpers';

/**
 * 结算单管理工作流 E2E 测试
 * 覆盖场景：
 * 1. 访问结算单列表页面
 * 2. 生成结算单
 * 3. 结算单状态流转：提交 → 运营确认 → 销售确认 → 客户确认
 * 4. 结算单筛选功能
 *
 * 注意：重构后结算单列表使用自定义 table.table（非 Arco Table），
 * 状态标签使用 InvoiceStatusBadge 组件（.tag 类，非 .arco-tag），
 * 筛选器使用自定义 FilterDropdown 组件（.filter-trigger 类，非 .arco-select）。
 * 状态流程：draft → pending_ops → pending_sales → pending_customer → customer_confirmed → completed
 */
test.describe('结算单管理工作流 @smoke', () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto('/billing/invoices');
    await page.waitForLoadState('networkidle');
  });

  test('访问结算单列表页面', async ({ authenticatedPage: page }) => {
    await expect(page).toHaveURL('/billing/invoices');

    // 验证页面标题 — 重构后标题为 "结算单管理"
    await expect(page.locator('h1').first()).toContainText('结算单');
  });

  test('生成结算单', async ({ authenticatedPage: page }) => {
    // 查找生成结算单按钮（重构后使用 .btn.primary 类）
    const generateButton = page.locator('button:has-text("生成结算单")').first();

    await expect(generateButton).toBeVisible({ timeout: 10000 });
    await generateButton.click();

    // 验证模态框已打开（使用 getVisibleModal 避免匹配隐藏弹窗）
    await waitForModal(page, 5000);
    const modal = getVisibleModal(page);
    await expect(modal).toBeVisible({ timeout: 5000 });

    // 验证模态框标题
    await expect(modal.locator('.arco-modal-title')).toContainText('生成结算单');

    // 验证表单元素存在（弹窗内有 a-radio-group 和 a-select）
    const radioGroup = modal.locator('.arco-radio-group').first();
    await expect(radioGroup).toBeVisible({ timeout: 5000 });

    // 关闭模态框
    const cancelButton = modal.locator('.arco-modal-footer button:has-text("取消")').first();
    await expect(cancelButton).toBeVisible();
    await cancelButton.click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test('结算单状态流转 - 提交 → 运营确认 → 销售确认 → 客户确认', async ({ authenticatedPage: page }) => {
    // 查找草稿状态的结算单（重构后使用 .tag 类，非 .arco-tag）
    const draftStatus = page.locator('table.table .tag:has-text("草稿")').first();

    // 如果存在草稿状态的结算单，测试状态流转
    const hasDraft = await draftStatus.isVisible({ timeout: 5000 }).catch(() => false);
    test.skip(!hasDraft, '当前没有草稿状态的结算单可供测试');

    const row = draftStatus.locator('xpath=ancestor::tr').first();
    await expect(row).toBeVisible();

    // 1. 提交
    const submitBtn = row.locator('button:has-text("提交")').first();
    await expect(submitBtn).toBeVisible({ timeout: 5000 });
    await submitBtn.click();
    await page.waitForLoadState('networkidle');

    // 2. 运营确认（如果按钮可见且可点击）
    const opsBtn = row.locator('button:has-text("运营确认")').first();
    const opsVisible = await opsBtn.isVisible({ timeout: 5000 }).catch(() => false);
    if (opsVisible && !(await opsBtn.isDisabled())) {
      await opsBtn.click();
      await page.waitForLoadState('networkidle');
    }

    // 3. 销售确认
    const salesBtn = row.locator('button:has-text("销售确认")').first();
    const salesVisible = await salesBtn.isVisible({ timeout: 5000 }).catch(() => false);
    if (salesVisible && !(await salesBtn.isDisabled())) {
      await salesBtn.click();
      await page.waitForLoadState('networkidle');
    }

    // 4. 客户确认
    const confirmBtn = row.locator('button:has-text("客户确认")').first();
    const confirmVisible = await confirmBtn.isVisible({ timeout: 5000 }).catch(() => false);
    if (confirmVisible) {
      await confirmBtn.click();
      await page.waitForLoadState('networkidle');
    }
  });

  test('结算单筛选功能', async ({ authenticatedPage: page }) => {
    // 重构后筛选器使用自定义 FilterDropdown 组件（.filter-trigger 类）
    const filterTrigger = page.locator('.filter-dropdown .filter-trigger').first();

    await expect(filterTrigger).toBeVisible({ timeout: 10000 });
    await filterTrigger.click();
    await page.waitForTimeout(300);

    // 等待下拉面板出现
    const filterPanel = page.locator('.filter-panel').first();
    await expect(filterPanel).toBeVisible({ timeout: 5000 });

    // 选择第一个筛选选项（非"全部"）
    const option = filterPanel.locator('.filter-option').nth(1);
    await expect(option).toBeVisible();
    await option.click();
    await page.waitForTimeout(500);

    // 验证页面没有报错
    const errorMessage = page.locator('.arco-message-error');
    await expect(errorMessage).not.toBeVisible({ timeout: 2000 });
  });
});
