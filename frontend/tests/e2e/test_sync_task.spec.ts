import { test, expect } from '@playwright/test';

/**
 * 同步任务 E2E 测试
 *
 * 测试策略：
 * - 使用 API mock 模拟后端响应
 * - 测试完整的同步流程
 * - 测试错误处理和取消功能
 */

test.describe('同步任务功能', () => {
  test.beforeEach(async ({ page }) => {
    // 登录
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');
  });

  test('应该成功创建同步任务并查看进度', async ({ page }) => {
    const taskId = 'test-task-123';

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
              task_id: taskId,
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

    // Mock 进度 API - 初始状态
    await page.route(`**/api/v1/sync-tasks/${taskId}/progress`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: {
            task_id: taskId,
            status: 'running',
            total_days: 1,
            completed_days: 0,
            skipped_days: 0,
            current_date: '2026-06-20',
            success_count: 0,
            failed_count: 0,
            percentage: 0,
            error_message: null,
          },
        }),
      });
    });

    // Mock 任务详情 API
    await page.route(`**/api/v1/sync-tasks/${taskId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: {
            task_id: taskId,
            status: 'running',
            start_date: '2026-06-20',
            end_date: '2026-06-20',
            sync_mode: 'skip_existing',
            total_days: 1,
            completed_days: 0,
            skipped_days: 0,
            current_date: '2026-06-20',
            success_count: 0,
            failed_count: 0,
            percentage: 0,
            error_message: null,
            created_at: new Date().toISOString(),
          },
        }),
      });
    });

    // 导航到消耗分析页面
    await page.goto('/analytics/consumption');
    await page.waitForLoadState('networkidle');

    // 点击数据同步按钮
    await page.click('button:has-text("数据同步")');

    // 等待对话框打开
    const dialog = page.locator('.arco-modal');
    await expect(dialog).toBeVisible();

    // 填写表单
    await page.fill('input[placeholder="开始日期"]', '2026-06-20');
    await page.fill('input[placeholder="结束日期"]', '2026-06-20');

    // 选择同步模式
    await page.click('text=仅补充缺失数据');

    // 提交表单
    await page.click('button:has-text("确定")');

    // 验证对话框关闭
    await expect(dialog).not.toBeVisible();

    // 验证成功提示
    await expect(page.locator('.arco-message-success')).toBeVisible();
    await expect(page.locator('.arco-message-success')).toContainText('同步任务已创建');

    // 导航到同步日志页面
    await page.click('text=查看任务');
    await page.waitForURL('/system/sync-logs');

    // 验证任务列表显示
    await expect(page.locator('table')).toBeVisible();
    await expect(page.locator('table')).toContainText(taskId);
  });

  test('应该显示同步进度', async ({ page }) => {
    const taskId = 'test-task-progress';

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
              task_id: taskId,
              status: 'running',
              start_date: '2026-06-20',
              end_date: '2026-06-22',
              sync_mode: 'skip_existing',
              total_days: 3,
              completed_days: 0,
              skipped_days: 0,
              current_date: '2026-06-20',
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

    // Mock 进度 API - 进行中
    let progressCallCount = 0;
    await page.route(`**/api/v1/sync-tasks/${taskId}/progress`, async (route) => {
      progressCallCount++;

      // 模拟进度变化
      const progress = Math.min(progressCallCount * 33, 100);
      const completedDays = Math.floor(progress / 33);

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: {
            task_id: taskId,
            status: progress >= 100 ? 'completed' : 'running',
            total_days: 3,
            completed_days: completedDays,
            skipped_days: 0,
            current_date: `2026-06-${20 + completedDays}`,
            success_count: completedDays * 100,
            failed_count: 0,
            percentage: progress,
            error_message: null,
          },
        }),
      });
    });

    // Mock 任务详情 API
    await page.route(`**/api/v1/sync-tasks/${taskId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: {
            task_id: taskId,
            status: 'running',
            start_date: '2026-06-20',
            end_date: '2026-06-22',
            sync_mode: 'skip_existing',
            total_days: 3,
            completed_days: 1,
            skipped_days: 0,
            current_date: '2026-06-21',
            success_count: 100,
            failed_count: 0,
            percentage: 33,
            error_message: null,
            created_at: new Date().toISOString(),
          },
        }),
      });
    });

    // 导航到消耗分析页面
    await page.goto('/analytics/consumption');
    await page.waitForLoadState('networkidle');

    // 点击数据同步按钮
    await page.click('button:has-text("数据同步")');

    // 等待对话框打开
    const dialog = page.locator('.arco-modal');
    await expect(dialog).toBeVisible();

    // 填写表单
    await page.fill('input[placeholder="开始日期"]', '2026-06-20');
    await page.fill('input[placeholder="结束日期"]', '2026-06-22');

    // 提交表单
    await page.click('button:has-text("确定")');

    // 验证对话框关闭
    await expect(dialog).not.toBeVisible();

    // 验证成功提示
    await expect(page.locator('.arco-message-success')).toBeVisible();

    // 点击"查看任务"按钮
    await page.click('text=查看任务');
    await page.waitForURL('/system/sync-logs');

    // 验证任务列表显示
    await expect(page.locator('table')).toBeVisible();

    // 点击任务查看详情
    await page.click(`text=${taskId}`);

    // 验证进度显示
    await expect(page.locator('.arco-progress')).toBeVisible();
    await expect(page.locator('.arco-progress-text')).toContainText('33%');
  });

  test('应该处理任务失败情况', async ({ page }) => {
    const taskId = 'test-task-failed';

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
              task_id: taskId,
              status: 'failed',
              start_date: '2026-06-20',
              end_date: '2026-06-20',
              sync_mode: 'skip_existing',
              total_days: 1,
              completed_days: 0,
              skipped_days: 0,
              current_date: null,
              success_count: 0,
              failed_count: 1,
              percentage: 0,
              error_message: '数据库连接失败',
              created_at: new Date().toISOString(),
            },
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Mock 进度 API - 失败状态
    await page.route(`**/api/v1/sync-tasks/${taskId}/progress`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: {
            task_id: taskId,
            status: 'failed',
            total_days: 1,
            completed_days: 0,
            skipped_days: 0,
            current_date: '2026-06-20',
            success_count: 0,
            failed_count: 1,
            percentage: 0,
            error_message: '数据库连接失败',
          },
        }),
      });
    });

    // Mock 任务详情 API
    await page.route(`**/api/v1/sync-tasks/${taskId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: {
            task_id: taskId,
            status: 'failed',
            start_date: '2026-06-20',
            end_date: '2026-06-20',
            sync_mode: 'skip_existing',
            total_days: 1,
            completed_days: 0,
            skipped_days: 0,
            current_date: null,
            success_count: 0,
            failed_count: 1,
            percentage: 0,
            error_message: '数据库连接失败',
            created_at: new Date().toISOString(),
          },
        }),
      });
    });

    // 导航到消耗分析页面
    await page.goto('/analytics/consumption');
    await page.waitForLoadState('networkidle');

    // 点击数据同步按钮
    await page.click('button:has-text("数据同步")');

    // 等待对话框打开
    const dialog = page.locator('.arco-modal');
    await expect(dialog).toBeVisible();

    // 填写表单
    await page.fill('input[placeholder="开始日期"]', '2026-06-20');
    await page.fill('input[placeholder="结束日期"]', '2026-06-20');

    // 提交表单
    await page.click('button:has-text("确定")');

    // 验证对话框关闭
    await expect(dialog).not.toBeVisible();

    // 验证成功提示（任务已创建，但执行失败）
    await expect(page.locator('.arco-message-success')).toBeVisible();

    // 点击"查看任务"按钮
    await page.click('text=查看任务');
    await page.waitForURL('/system/sync-logs');

    // 验证任务列表显示失败状态
    await expect(page.locator('table')).toBeVisible();
    await expect(page.locator('table')).toContainText('失败');

    // 点击任务查看详情
    await page.click(`text=${taskId}`);

    // 验证错误信息显示
    await expect(page.locator('.arco-alert-error')).toBeVisible();
    await expect(page.locator('.arco-alert-error')).toContainText('数据库连接失败');
  });

  test('应该能够取消正在执行的任务', async ({ page }) => {
    const taskId = 'test-task-cancel';

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
              task_id: taskId,
              status: 'running',
              start_date: '2026-06-20',
              end_date: '2026-06-25',
              sync_mode: 'skip_existing',
              total_days: 6,
              completed_days: 2,
              skipped_days: 0,
              current_date: '2026-06-22',
              success_count: 200,
              failed_count: 0,
              percentage: 33,
              error_message: null,
              created_at: new Date().toISOString(),
            },
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Mock 取消任务 API
    await page.route(`**/api/v1/sync-tasks/${taskId}/cancel`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: null,
        }),
      });
    });

    // Mock 进度 API - 取消后
    await page.route(`**/api/v1/sync-tasks/${taskId}/progress`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: {
            task_id: taskId,
            status: 'cancelled',
            total_days: 6,
            completed_days: 2,
            skipped_days: 0,
            current_date: '2026-06-22',
            success_count: 200,
            failed_count: 0,
            percentage: 33,
            error_message: null,
          },
        }),
      });
    });

    // Mock 任务详情 API
    await page.route(`**/api/v1/sync-tasks/${taskId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'success',
          data: {
            task_id: taskId,
            status: 'cancelled',
            start_date: '2026-06-20',
            end_date: '2026-06-25',
            sync_mode: 'skip_existing',
            total_days: 6,
            completed_days: 2,
            skipped_days: 0,
            current_date: '2026-06-22',
            success_count: 200,
            failed_count: 0,
            percentage: 33,
            error_message: null,
            created_at: new Date().toISOString(),
          },
        }),
      });
    });

    // 导航到消耗分析页面
    await page.goto('/analytics/consumption');
    await page.waitForLoadState('networkidle');

    // 点击数据同步按钮
    await page.click('button:has-text("数据同步")');

    // 等待对话框打开
    const dialog = page.locator('.arco-modal');
    await expect(dialog).toBeVisible();

    // 填写表单
    await page.fill('input[placeholder="开始日期"]', '2026-06-20');
    await page.fill('input[placeholder="结束日期"]', '2026-06-25');

    // 提交表单
    await page.click('button:has-text("确定")');

    // 验证对话框关闭
    await expect(dialog).not.toBeVisible();

    // 验证成功提示
    await expect(page.locator('.arco-message-success')).toBeVisible();

    // 点击"查看任务"按钮
    await page.click('text=查看任务');
    await page.waitForURL('/system/sync-logs');

    // 验证任务列表显示
    await expect(page.locator('table')).toBeVisible();

    // 点击任务查看详情
    await page.click(`text=${taskId}`);

    // 点击取消按钮
    await page.click('button:has-text("取消任务")');

    // 验证确认对话框
    const confirmDialog = page.locator('.arco-modal');
    await expect(confirmDialog).toBeVisible();
    await expect(confirmDialog).toContainText('确认取消');

    // 确认取消
    await page.click('.arco-modal button:has-text("确定")');

    // 验证取消成功提示
    await expect(page.locator('.arco-message-success')).toBeVisible();
    await expect(page.locator('.arco-message-success')).toContainText('任务已取消');

    // 验证状态更新为已取消
    await expect(page.locator('.arco-tag')).toContainText('已取消');
  });

  test('应该验证日期范围', async ({ page }) => {
    // 导航到消耗分析页面
    await page.goto('/analytics/consumption');
    await page.waitForLoadState('networkidle');

    // 点击数据同步按钮
    await page.click('button:has-text("数据同步")');

    // 等待对话框打开
    const dialog = page.locator('.arco-modal');
    await expect(dialog).toBeVisible();

    // 测试结束日期早于开始日期
    await page.fill('input[placeholder="开始日期"]', '2026-06-25');
    await page.fill('input[placeholder="结束日期"]', '2026-06-20');

    // 尝试提交
    await page.click('button:has-text("确定")');

    // 验证错误提示
    await expect(page.locator('.arco-message-error')).toBeVisible();
    await expect(page.locator('.arco-message-error')).toContainText('结束日期不能早于开始日期');

    // 测试超过 31 天限制
    await page.fill('input[placeholder="开始日期"]', '2026-01-01');
    await page.fill('input[placeholder="结束日期"]', '2026-12-31');

    // 尝试提交
    await page.click('button:has-text("确定")');

    // 验证错误提示
    await expect(page.locator('.arco-message-error')).toBeVisible();
    await expect(page.locator('.arco-message-error')).toContainText('时间跨度不能超过 31 天');
  });
});
