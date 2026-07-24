import { test, expect } from './fixtures';
import { getVisibleModal, waitForModal } from './test-helpers';

/**
 * 同步任务 E2E 测试
 *
 * 测试策略：
 * - 使用 API mock 模拟后端响应
 * - 测试完整的同步流程
 * - 测试错误处理和取消功能
 *
 * 注意：SyncDialog 组件使用 a-date-picker（非 a-range-picker），
 * okText 为 "提交同步任务"，成功后弹出 Modal.success（非 Message.success）。
 */

// ===================== 辅助函数 =====================

function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

async function navigateToSyncDialog(page: import('@playwright/test').Page) {
  await page.goto('/analytics/consumption', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(1500);
  await page.getByRole('button', { name: /数据同步/ }).first().click();
  await waitForModal(page);
}

async function selectDates(page: import('@playwright/test').Page, startDate: string, endDate: string) {
  const modal = getVisibleModal(page);
  const datePickers = modal.locator('.arco-picker');
  await datePickers.first().waitFor({ state: 'visible', timeout: 5000 });

  // 开始日期
  await datePickers.first().click();
  await page.waitForTimeout(300);
  await datePickers.first().locator('input').fill(startDate);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);

  // 结束日期
  await datePickers.nth(1).click();
  await page.waitForTimeout(300);
  await datePickers.nth(1).locator('input').fill(endDate);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
}

// ===================== 测试用例 =====================

test.describe('同步任务功能', () => {

  test('应该成功创建同步任务', async ({ authenticatedPage: page }) => {
    test.setTimeout(60000);

    // Mock 创建任务 API
    await page.route('**/api/v1/sync-tasks', async (route) => {
      const request = route.request();
      if (request.method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 0,
            message: 'success',
            data: {
              task_id: 'test-task-123',
              status: 'pending',
              start_date: '2026-06-20',
              end_date: '2026-06-20',
              sync_mode: 'skip_existing',
              total_days: 1,
              completed_days: 0,
              skipped_days: 0,
              current_date: null,
              success_count: 0,
              failed_count: 0,
              percentage: 0,
              error_message: null,
              created_at: new Date().toISOString(),
            },
          }),
        });
      } else {
        await route.continue();
      }
    });

    await navigateToSyncDialog(page);

    const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const endDate = new Date();
    await selectDates(page, formatDate(startDate), formatDate(endDate));

    // 提交表单 — okText 为 "提交同步任务"
    const modal = getVisibleModal(page);
    const submitBtn = modal.locator('.arco-modal-footer').getByRole('button', { name: /提交同步任务/ });
    await submitBtn.click();

    // SyncDialog 创建成功后关闭弹窗，弹出 Modal.success
    // Modal.success 标题为 "任务创建成功"，包含 "查看任务" 按钮
    const successModal = page.locator('.arco-modal:visible').filter({ hasText: '任务创建成功' });
    await expect(successModal.first()).toBeVisible({ timeout: 15000 });

    // 点击 "查看任务" 跳转到同步日志页面
    await successModal.locator('button:has-text("查看任务")').click();
    await page.waitForURL('/system/sync-logs', { timeout: 10000 });
  });

  test('应该处理任务失败情况', async ({ authenticatedPage: page }) => {
    test.setTimeout(60000);

    // Mock 创建任务 API - 返回错误
    await page.route('**/api/v1/sync-tasks', async (route) => {
      const request = route.request();
      if (request.method() === 'POST') {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 400,
            message: '无效的请求参数',
            data: null,
          }),
        });
      } else {
        await route.continue();
      }
    });

    await navigateToSyncDialog(page);

    const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const endDate = new Date();
    await selectDates(page, formatDate(startDate), formatDate(endDate));

    // 提交表单
    const modal = getVisibleModal(page);
    const submitBtn = modal.locator('.arco-modal-footer').getByRole('button', { name: /提交同步任务/ });
    await submitBtn.click();

    // 验证错误消息出现（Message.error）
    await expect(page.locator('.arco-message-error').first()).toBeVisible({ timeout: 10000 });

    // 弹窗应保持打开状态
    const modalTitle = getVisibleModal(page).locator('.arco-modal-title');
    await expect(modalTitle).toBeVisible();
    await expect(modalTitle).toHaveText('数据同步');
  });

  test('应该验证日期范围 — 结束日期早于开始日期', async ({ authenticatedPage: page }) => {
    test.setTimeout(60000);

    await navigateToSyncDialog(page);

    // 设置结束日期早于开始日期
    await selectDates(page, '2026-06-25', '2026-06-20');

    // 提交表单
    const modal = getVisibleModal(page);
    const submitBtn = modal.locator('.arco-modal-footer').getByRole('button', { name: /提交同步任务/ });
    await submitBtn.click();

    // 验证错误提示（可能是 a-alert 或 Message.error）
    const errorAlert = page.locator('.arco-alert-error, .arco-form-item-error-message');
    const errorMessage = page.locator('.arco-message-error');
    await expect(errorAlert.or(errorMessage).first()).toBeVisible({ timeout: 10000 });
  });

  test('应该验证日期范围 — 超过31天', async ({ authenticatedPage: page }) => {
    test.setTimeout(60000);

    await navigateToSyncDialog(page);

    // 设置时间跨度超过31天
    await selectDates(page, '2026-01-01', '2026-12-31');

    // 提交表单
    const modal = getVisibleModal(page);
    const submitBtn = modal.locator('.arco-modal-footer').getByRole('button', { name: /提交同步任务/ });
    await submitBtn.click();

    // 验证错误提示
    const errorAlert = page.locator('.arco-alert-error, .arco-form-item-error-message');
    const errorMessage = page.locator('.arco-message-error');
    await expect(errorAlert.or(errorMessage).first()).toBeVisible({ timeout: 10000 });
  });

  test('同步模式切换 — 显示警告提示', async ({ authenticatedPage: page }) => {
    test.setTimeout(60000);

    await navigateToSyncDialog(page);

    // 点击"强制覆盖已有数据"
    const modal = getVisibleModal(page);
    const forceOverwriteRadio = modal.locator('.arco-radio').nth(1);
    await forceOverwriteRadio.click();

    // 验证警告提示出现
    const warningAlert = modal.locator('.arco-alert-warning');
    await expect(warningAlert).toBeVisible();
    await expect(warningAlert).toContainText('删除并重新同步');

    // 切回"仅补充缺失数据"
    const skipExistingRadio = modal.locator('.arco-radio').first();
    await skipExistingRadio.click();
    await expect(warningAlert).not.toBeVisible({ timeout: 3000 });
  });
});
