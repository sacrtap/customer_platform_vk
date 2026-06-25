import { test, expect } from './fixtures';
import { waitForModal, waitForMessage } from './test-helpers';
import type { Page } from '@playwright/test';

/**
 * 数据同步功能 E2E 测试
 *
 * 测试策略：
 * - UI 交互测试（日期验证、模式切换）直接验证前端行为
 * - 同步流程测试使用 API mock 模拟后端响应
 */

// ===================== 辅助函数 =====================

function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

async function navigateToSyncDialog(page: Page) {
  await page.goto('/analytics/consumption');
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: /数据同步/ }).first().click();
  await waitForModal(page);
}

async function selectDateRange(page: Page, startDate: Date, endDate: Date) {
  const datePickers = page.locator('.arco-picker');
  const startPicker = datePickers.first();
  await startPicker.click();
  await startPicker.locator('input').fill(formatDate(startDate));
  await page.keyboard.press('Enter');

  const endPicker = datePickers.nth(1);
  await endPicker.click();
  await endPicker.locator('input').fill(formatDate(endDate));
  await page.keyboard.press('Enter');
}

/**
 * Mock 同步任务创建 API
 */
async function mockCreateSyncTask(page: Page, taskId: string = 'test-task-123') {
  await page.route('/api/v1/sync-tasks', route => {
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

/**
 * Mock 同步任务进度 API
 */
async function mockSyncProgress(page: Page, taskId: string, progress: {
  status?: string;
  percentage?: number;
  completed_days?: number;
  total_days?: number;
}) {
  await page.route(`**/sync-tasks/${taskId}/progress`, route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        message: 'success',
        data: {
          task_id: taskId,
          status: progress.status || 'running',
          sync_mode: 'skip_existing',
          total_days: progress.total_days || 7,
          completed_days: progress.completed_days || 0,
          skipped_days: 0,
          current_date: formatDate(new Date()),
          success_count: 10,
          failed_count: 0,
          percentage: progress.percentage || 0,
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

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).toHaveText('数据同步');

      const datePickers = page.locator('.arco-picker');
      await expect(datePickers.first()).toBeVisible();
      await expect(datePickers.nth(1)).toBeVisible();

      const radioGroup = page.locator('.arco-radio-group');
      await expect(radioGroup).toBeVisible();

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await expect(startButton).toBeVisible();
    });

    test('日期验证 - 结束日期早于开始日期显示错误', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const today = new Date();
      const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
      await selectDateRange(page, today, yesterday);

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await startButton.click();

      await waitForMessage(page, 'error');

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).toBeVisible();
    });

    test('日期验证 - 时间跨度超过31天显示错误', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const startDate = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await startButton.click();

      await waitForMessage(page, 'error');

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).toBeVisible();
    });

    test('同步模式切换 - 显示警告提示', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const skipExistingLabel = page.getByText('仅补充缺失数据');
      await expect(skipExistingLabel).toBeVisible();

      // 点击"强制覆盖已有数据"（限定在最后一个 Modal 内查找）
      const syncModal = page.locator('.arco-modal').last();
      const forceOverwriteRadio = syncModal.locator('.arco-radio').nth(1);
      await forceOverwriteRadio.click();

      const warningAlert = page.locator('.arco-alert');
      await expect(warningAlert).toBeVisible();
      await expect(warningAlert).toContainText('删除并重新同步');

      await skipExistingLabel.click();
      await expect(warningAlert).not.toBeVisible({ timeout: 3000 });
    });

    test('关闭对话框 - 点击取消按钮', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const cancelButton = page.locator('.arco-modal-footer').getByRole('button', { name: '取消' });
      await cancelButton.click();

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).not.toBeVisible({ timeout: 5000 });
    });

    test('关闭对话框 - 点击关闭图标', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      const closeButton = page.locator('.arco-modal-close-btn').last();
      await closeButton.click();

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).not.toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('同步流程测试（使用 API Mock）', () => {

    test('创建同步任务 - 显示进度', async ({ authenticatedPage: page }) => {
      test.setTimeout(60000);

      await navigateToSyncDialog(page);

      const taskId = 'test-task-' + Date.now();
      await mockCreateSyncTask(page, taskId);
      await mockSyncProgress(page, taskId, {
        status: 'running',
        percentage: 30,
        completed_days: 2,
        total_days: 7,
      });

      const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await startButton.click();

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).toHaveText('同步中...', { timeout: 10000 });

      const progressBar = page.locator('.arco-progress');
      await expect(progressBar).toBeVisible({ timeout: 10000 });

      const cancelButton = page.locator('.arco-modal-footer').getByRole('button', { name: '取消' });
      await expect(cancelButton).toBeVisible();
    });

    test('同步完成 - 显示完成状态', async ({ authenticatedPage: page }) => {
      test.setTimeout(60000);

      await navigateToSyncDialog(page);

      const taskId = 'test-task-completed-' + Date.now();
      await mockCreateSyncTask(page, taskId);
      await mockSyncProgress(page, taskId, {
        status: 'completed',
        percentage: 100,
        completed_days: 7,
        total_days: 7,
      });

      const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await startButton.click();

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).toHaveText('同步完成', { timeout: 15000 });

      const statsSection = page.locator('.stats');
      await expect(statsSection).toBeVisible();

      const closeButton = page.locator('.arco-modal-footer').getByRole('button', { name: /关闭|确定/ }).first();
      await expect(closeButton).toBeVisible();
    });

    test('同步失败 - 显示失败状态', async ({ authenticatedPage: page }) => {
      test.setTimeout(60000);

      await navigateToSyncDialog(page);

      const taskId = 'test-task-failed-' + Date.now();
      await mockCreateSyncTask(page, taskId);
      await mockSyncProgress(page, taskId, {
        status: 'failed',
        percentage: 50,
        completed_days: 3,
        total_days: 7,
      });

      const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await startButton.click();

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).toHaveText('同步失败', { timeout: 15000 });

      const retryButton = page.locator('.arco-modal-footer').getByRole('button', { name: '重试' });
      await expect(retryButton).toBeVisible();
    });

    test('取消同步任务 - 显示取消状态', async ({ authenticatedPage: page }) => {
      test.setTimeout(60000);

      await navigateToSyncDialog(page);

      const taskId = 'test-task-cancel-' + Date.now();
      await mockCreateSyncTask(page, taskId);
      await mockSyncProgress(page, taskId, {
        status: 'running',
        percentage: 30,
        completed_days: 2,
        total_days: 7,
      });

      const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await startButton.click();

      const progressBar = page.locator('.arco-progress');
      await expect(progressBar).toBeVisible({ timeout: 10000 });

      await page.route(`**/sync-tasks/${taskId}/cancel`, route => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ code: 0, message: 'success', data: null }),
        });
      });

      await mockSyncProgress(page, taskId, {
        status: 'cancelled',
        percentage: 30,
        completed_days: 2,
        total_days: 7,
      });

      const cancelButton = page.locator('.arco-modal-footer').getByRole('button', { name: '取消' });
      await cancelButton.click();

      await waitForMessage(page, 'info');

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).toHaveText('同步已取消', { timeout: 15000 });
    });

    test('进度动态更新 - 验证百分比实时变化', async ({ authenticatedPage: page }) => {
      test.setTimeout(60000);

      await navigateToSyncDialog(page);

      const taskId = 'test-task-progress-' + Date.now();
      await mockCreateSyncTask(page, taskId);

      // 第一次返回 20% 进度
      await mockSyncProgress(page, taskId, {
        status: 'running',
        percentage: 0.2,
        completed_days: 1,
        total_days: 5,
      });

      const startDate = new Date(Date.now() - 5 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await startButton.click();

      // 验证进度条可见
      const progressBar = page.locator('.arco-progress');
      await expect(progressBar).toBeVisible({ timeout: 10000 });

      // 验证初始进度 20%（ProgressView 将 0.2 * 100 = 20%）
      await expect(progressBar).toContainText('20%', { timeout: 10000 });

      // 更新 mock 返回 60% 进度
      await mockSyncProgress(page, taskId, {
        status: 'running',
        percentage: 0.6,
        completed_days: 3,
        total_days: 5,
      });

      // 等待进度更新到 60%（轮询间隔 2 秒）
      await expect(progressBar).toContainText('60%', { timeout: 10000 });

      // 更新 mock 返回 100% 进度
      await mockSyncProgress(page, taskId, {
        status: 'completed',
        percentage: 1.0,
        completed_days: 5,
        total_days: 5,
      });

      // 验证最终进度 100%
      await expect(progressBar).toContainText('100%', { timeout: 10000 });

      // 验证状态变为完成
      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).toHaveText('同步完成', { timeout: 5000 });
    });

    test('后端错误 - 显示错误消息', async ({ authenticatedPage: page }) => {
      await navigateToSyncDialog(page);

      await page.route('/api/v1/sync-tasks', route => {
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

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await startButton.click();

      await waitForMessage(page, 'error');

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).toBeVisible();
      await expect(modalTitle).toHaveText('数据同步');
    });
  });

  test.describe('最小化功能测试', () => {

    test('最小化进度框 - 按钮显示百分比', async ({ authenticatedPage: page }) => {
      test.setTimeout(60000);

      await navigateToSyncDialog(page);

      const taskId = 'test-task-minimize-' + Date.now();
      await mockCreateSyncTask(page, taskId);
      await mockSyncProgress(page, taskId, {
        status: 'running',
        percentage: 0.45,
        completed_days: 3,
        total_days: 7,
      });

      const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await startButton.click();

      const progressBar = page.locator('.arco-progress');
      await expect(progressBar).toBeVisible({ timeout: 10000 });

      const closeButton = page.locator('.arco-modal-close-btn').last();
      await closeButton.click();

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).not.toBeVisible({ timeout: 3000 });

      const syncButton = page.getByRole('button', { name: /数据同步/ }).first();
      await expect(syncButton).toContainText('45%', { timeout: 5000 });
      await expect(syncButton).toBeDisabled();
    });

    test('重新打开最小化的进度框', async ({ authenticatedPage: page }) => {
      test.setTimeout(60000);

      await navigateToSyncDialog(page);

      const taskId = 'test-task-reopen-' + Date.now();
      await mockCreateSyncTask(page, taskId);
      await mockSyncProgress(page, taskId, {
        status: 'running',
        percentage: 0.6,
        completed_days: 4,
        total_days: 7,
      });

      const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const endDate = new Date();
      await selectDateRange(page, startDate, endDate);

      const startButton = page.locator('.arco-modal-footer').getByRole('button', { name: /开始同步|确定/ });
      await startButton.click();

      await expect(page.locator('.arco-progress')).toBeVisible({ timeout: 10000 });

      await page.locator('.arco-modal-close-btn').last().click();
      await page.waitForTimeout(1000);

      const syncButton = page.getByRole('button', { name: /数据同步/ }).first();
      await syncButton.click();

      const modalTitle = page.locator('.arco-modal-title').last();
      await expect(modalTitle).toHaveText('同步中...', { timeout: 5000 });

      await expect(page.locator('.arco-progress')).toBeVisible();
    });
  });
});
