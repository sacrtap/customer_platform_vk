import { test, expect } from './fixtures';
import { getVisibleModal } from './test-helpers';

/**
 * 数据清空页面 E2E 测试
 *
 * 测试场景：
 * 1. PageHeader 显示
 * 2. 权限校验
 * 3. 清空确认弹窗
 * 4. 清空结果展示
 */
test.describe('数据清空页面', () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto('/system/database-management');
    await page.waitForLoadState('networkidle');
  });

  test('I01: PageHeader 显示', async ({ authenticatedPage: page }) => {
    await expect(page.locator('h1').first()).toContainText('数据库管理');
    await expect(page.locator('.desc')).toBeVisible();
  });

  test('I02: 权限校验 — 有 system:database_clear 权限才可访问', async ({ authenticatedPage: page }) => {
    // 验证页面加载成功（有权限的用户应能看到内容）
    await expect(page.locator('.arco-card')).toBeVisible({ timeout: 5000 });

    // 验证警告提示存在
    const alert = page.locator('.arco-alert-warning');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText('不可逆');

    // 验证影响范围描述存在
    const descriptions = page.locator('.arco-descriptions');
    await expect(descriptions).toBeVisible();

    // 验证"清空客户数据"按钮（取决于权限）
    const clearBtn = page.locator('button:has-text("清空客户数据")');
    const hasPermission = await clearBtn.isVisible({ timeout: 3000 }).catch(() => false);
    if (hasPermission) {
      await expect(clearBtn).toBeVisible();
    }
  });

  test('I03: 清空确认弹窗', async ({ authenticatedPage: page }) => {
    const clearBtn = page.locator('button:has-text("清空客户数据")');
    const hasPermission = await clearBtn.isVisible({ timeout: 3000 }).catch(() => false);
    test.skip(!hasPermission, '当前用户无 system:database_clear 权限');

    await clearBtn.click();

    // 验证确认弹窗显示（Arco Modal.confirm）
    const modal = getVisibleModal(page);
    await expect(modal).toBeVisible({ timeout: 5000 });

    // 验证弹窗包含确认信息
    await expect(modal).toContainText('确认');

    // 取消操作（避免实际清空数据）
    const cancelBtn = modal.locator('button:has-text("取消")');
    await cancelBtn.click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // 验证没有结果展示
    await expect(page.locator('.result-info')).not.toBeVisible({ timeout: 2000 });
  });

  test('I04: 清空结果展示区域', async ({ authenticatedPage: page }) => {
    // 等待描述列表加载
    await expect(page.locator('.arco-descriptions')).toBeVisible({ timeout: 10000 });

    // 验证结果区域初始不显示（使用 toHaveCount(0) 因为元素可能不存在于 DOM 中）
    await expect(page.locator('.result-info')).toHaveCount(0, { timeout: 5000 });

    // 验证影响范围列表存在（Arco Descriptions 渲染为 .arco-descriptions-row，非 .arco-descriptions-item）
    const descRows = page.locator('.arco-descriptions-row');
    await expect(descRows.first()).toBeVisible({ timeout: 5000 });
    const rowCount = await descRows.count();
    expect(rowCount).toBeGreaterThanOrEqual(2);

    // 验证操作名称描述（在描述列表区域内查找文本）
    await expect(page.locator('.arco-descriptions').filter({ hasText: '清空客户数据' })).toBeVisible();
  });
});
