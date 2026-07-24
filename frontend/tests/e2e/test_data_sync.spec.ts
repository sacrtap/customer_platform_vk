import { test, expect } from './fixtures';
import { waitForModal, waitForMessage, getVisibleModal } from './test-helpers';
import type { Page } from '@playwright/test';

/**
 * 数据同步功能 E2E 测试
 *
 * 测试策略：
 * - UI 交互测试（日期验证、模式切换）直接验证前端行为
 * - 同步流程测试使用 API mock 模拟后端响应
 *
 * 注意：SyncDialog 组件创建任务后会关闭弹窗并显示成功提示框，
 * 不在弹窗内做内联进度轮询。测试已适配此行为。
 */

// ===================== 辅助函数 =====================

function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

async function navigateToSyncDialog(page: Page) {
  await page.goto('/analytics/consumption', { waitUntil: 'domcontentloaded', timeout: 30000 });
  // 等待页面基本元素加载（不用 networkidle，避免超时）
  await page.waitForTimeout(1000);
  await page.getByRole('button', { name: /数据同步/ }).first().click();
  await waitForModal(page);
}

async function selectDateRange(page: Page, startDate: Date, endDate: Date) {
  const datePickers = page.locator('.arco-picker');
  await datePickers.first().waitFor({ state: 'visible', timeout: 5000 });

  const startPicker = datePickers.first();
  await startPicker.click();
  await page.waitForTimeout(300);
  await startPicker.locator('input').fill(formatDate(startDate));
  await page.keyboard.press('Enter');

  const endPicker = datePickers.nth(1);
  await endPicker.click();
  await page.waitForTimeout(300);
  await endPicker.locator('input').fill(formatDate(endDate));
  await page.keyboard.press('Enter');
}

/**
 * Mock 同步任务创建 API
 */
async function mockCreateSyncTask(page: Page, taskId: string = 'test-task-123') {
  await page.route('**/api/v1/sync-tasks', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        message: 'success',
        data: {
          task_id: taskId,
          status: 'running',
          sync_mode: 'skip_existing',
          total_days: 7,
          completed_days: 0,
          skipped_days: 0,
          current_date: formatDate(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)),
          success_count: 0,
          failed_count: 0,
          percentage: 0,
          error_message: null,
        }
      }),
    });
  });
}

// ===================== 测试用例 =====================

test.describe('数据同步功能', () => {

  test.describe('UI 交互测试', () => {

    test('打开同步对话框 - 显示默认状态', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const modal = getVisibleModal(page);
      const modalTitle = modal.locator('.arco-modal-title');
      await expect(modalTitle).toHaveText('数据同步');

      const datePickers = page.locator('.arco-picker');
      await expect(datePickers.first()).toBeVisible();
      await expect(datePickers.nth(1)).toBeVisible();

      const radioGroup = page.locator('.arco-radio-group');
      await expect(radioGroup).toBeVisible();

      // okText 在 input 状态下为"提交同步任务"
      const startButton = modal.locator('.arco-modal-footer').getByRole('button', { name: /提交同步任务|确定/ });
      await expect(startButton).toBeVisible();
    });

    test('日期验证 - 结束日期早于开始日期显示错误', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const today = new Date();
      const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
      await selectDateRange(page, today, yesterday);

      const modal = getVisibleModal(page);
      const startButton = modal.locator('.arco-modal-footer').getByRole('button', { name: /提交同步任务|确定/ });
      await startButton.click();

      // 组件会显示日期错误提示（a-alert type="error" 或 Message.error）
      const errorAlert = page.locator('.arco-alert-error, .arco-form-item-error-message');
      const errorMessage = page.locator('.arco-message-error');
      await expect(errorAlert.or(errorMessage).first()).toBeVisible({ timeout: 10000 });
    });

    test('日期验证 - 时间跨度超过31天显示错误', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const startDate = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const modal = getVisibleModal(page);
      const startButton = modal.locator('.arco-modal-footer').getByRole('button', { name: /提交同步任务|确定/ });
      await startButton.click();

      const errorAlert = page.locator('.arco-alert-error, .arco-form-item-error-message');
      const errorMessage = page.locator('.arco-message-error');
      await expect(errorAlert.or(errorMessage).first()).toBeVisible({ timeout: 10000 });
    });

    test('同步模式切换 - 显示警告提示', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const skipExistingLabel = page.getByText('仅补充缺失数据');
      await expect(skipExistingLabel).toBeVisible();

      // 点击"强制覆盖已有数据"（限定在可见 Modal 内查找）
      const syncModal = getVisibleModal(page);
      const forceOverwriteRadio = syncModal.locator('.arco-radio').nth(1);
      await forceOverwriteRadio.click();

      const warningAlert = page.locator('.arco-alert-warning');
      await expect(warningAlert).toBeVisible();
      await expect(warningAlert).toContainText('删除并重新同步');

      await skipExistingLabel.click();
      await expect(warningAlert).not.toBeVisible({ timeout: 3000 });
    });

    test('关闭对话框 - 点击取消按钮', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const modal = getVisibleModal(page);
      const cancelButton = modal.locator('.arco-modal-footer').getByRole('button', { name: '取消' });
      await cancelButton.click();

      // 验证弹窗关闭
      await expect(page.locator('.arco-modal:visible')).toHaveCount(0, { timeout: 5000 });
    });

    test('关闭对话框 - 点击关闭图标', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const modal = getVisibleModal(page);
      const closeButton = modal.locator('.arco-modal-close-btn');
      await closeButton.click();

      // 验证弹窗关闭
      await expect(page.locator('.arco-modal:visible')).toHaveCount(0, { timeout: 5000 });
    });
  });

  test.describe('同步流程测试（使用 API Mock）', () => {

    test('创建同步任务 - 成功后显示提示', async ({ authenticatedPage: page }) => {
      test.setTimeout(60000);

      await navigateToSyncDialog(page);

      const taskId = 'test-task-' + Date.now();
      await mockCreateSyncTask(page, taskId);

      const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const modal = getVisibleModal(page);
      const startButton = modal.locator('.arco-modal-footer').getByRole('button', { name: /提交同步任务|确定/ });
      await startButton.click();

      // SyncDialog 创建任务后会关闭弹窗并显示 Modal.success 成功提示
      // 等待成功提示出现（可能是 Arco Message 或 Modal.success）
      const successMessage = page.locator('.arco-message-success');
      const successModal = page.locator('.arco-modal:visible').locator('.arco-modal-title', { hasText: /成功/ });

      // 至少应该出现一种成功反馈
      await expect(successMessage.or(successModal).first()).toBeVisible({ timeout: 15000 });
    });

    test('后端错误 - 显示错误消息', async ({ authenticatedPage: page }) => {
      test.setTimeout(60000);

      await navigateToSyncDialog(page);

      await page.route('**/api/v1/sync-tasks', route => {
        route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 400,
            message: '无效的请求参数',
            data: null
          }),
        });
      });

      const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const modal = getVisibleModal(page);
      const startButton = modal.locator('.arco-modal-footer').getByRole('button', { name: /提交同步任务|确定/ });
      await startButton.click();

      // 验证错误消息出现
      await waitForMessage(page, 'error');

      // 弹窗应保持打开状态
      const modalTitle = getVisibleModal(page).locator('.arco-modal-title');
      await expect(modalTitle).toBeVisible();
      await expect(modalTitle).toHaveText('数据同步');
    });
  });

  test.describe('最小化功能测试', () => {
    // 注意：SyncDialog 组件当前不在弹窗内做进度轮询，
    // 创建任务后直接关闭弹窗并显示成功提示。
    // 最小化/进度轮询功能未在当前组件中实现，
    // 这些测试暂时跳过。

    test.skip('最小化进度框 - 按钮显示百分比', async ({ authenticatedPage: _page }) => {
      // SKIP: SyncDialog 不支持内联进度轮询
    });

    test.skip('重新打开最小化的进度框', async ({ authenticatedPage: _page }) => {
      // SKIP: SyncDialog 不支持内联进度轮询
    });

    test.skip('同步完成 - 显示完成状态', async ({ authenticatedPage: _page }) => {
      // SKIP: SyncDialog 创建任务后关闭弹窗，不显示内联完成状态
    });

    test.skip('同步失败 - 显示失败状态', async ({ authenticatedPage: _page }) => {
      // SKIP: SyncDialog 创建任务后关闭弹窗，不显示内联失败状态
    });

    test.skip('取消同步任务 - 显示取消状态', async ({ authenticatedPage: _page }) => {
      // SKIP: SyncDialog 创建任务后关闭弹窗，不显示内联取消状态
    });

    test.skip('进度动态更新 - 验证百分比实时变化', async ({ authenticatedPage: _page }) => {
      // SKIP: SyncDialog 不支持内联进度轮询
    });
  });
});
