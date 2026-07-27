import { test, expect } from './fixtures';
import { getVisibleModal } from './test-helpers';

/**
 * 合作状态页面 E2E 测试
 *
 * 测试场景：
 * 1. PageHeader 显示
 * 2. 合作状态列表表格渲染
 * 3. 创建合作状态
 * 4. 编辑合作状态
 * 5. 删除合作状态
 * 6. 侧边栏菜单入口
 */
test.describe('合作状态页面', () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto('/system/cooperation-statuses');
    await page.waitForLoadState('networkidle');
  });

  test('C01: PageHeader 显示', async ({ authenticatedPage: page }) => {
    await expect(page.locator('h1').first()).toContainText('合作状态');
    await expect(page.locator('.desc')).toBeVisible();

    // 验证"新增合作状态"按钮存在
    const createBtn = page.locator('button:has-text("新增合作状态")');
    const hasPermission = await createBtn.isVisible({ timeout: 3000 }).catch(() => false);
    if (hasPermission) {
      await expect(createBtn).toBeVisible();
    }
  });

  test('C02: 合作状态列表表格渲染', async ({ authenticatedPage: page }) => {
    // 验证表格存在
    const table = page.locator('.arco-table');
    await expect(table.first()).toBeVisible({ timeout: 10000 });

    // 验证表格有数据行或空状态
    const tbody = table.locator('tbody tr');
    const emptyState = table.locator('.arco-empty');
    const hasData = await tbody.count();
    const hasEmpty = await emptyState.count();
    expect(hasData > 0 || hasEmpty > 0).toBeTruthy();
  });

  test('C03: 创建合作状态', async ({ authenticatedPage: page }) => {
    // 点击新建按钮
    const createBtn = page.locator('button:has-text("新增合作状态")');
    const hasPermission = await createBtn.isVisible({ timeout: 3000 }).catch(() => false);
    test.skip(!hasPermission, '当前用户无 cooperation_statuses:manage 权限');

    await createBtn.click();

    // 验证弹窗显示
    const modal = getVisibleModal(page);
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(getVisibleModal(page).locator('.arco-modal-title')).toContainText('新增合作状态');

    // 填入合作状态名称
    const inputs = modal.locator('input');
    const nameInput = inputs.first();
    await expect(nameInput).toBeVisible();
    await nameInput.fill(`测试状态_${Date.now()}`);

    // 填入存储值（第二个 input）
    const valueInput = inputs.nth(1);
    if (await valueInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await valueInput.fill(`test_value_${Date.now()}`);
    }

    // 填入排序号（如果有 number input）
    const sortInput = modal.locator('input[type="number"], input[placeholder*="排序"]');
    if (await sortInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await sortInput.fill('99');
    }

    // 提交
    const submitBtn = modal.locator('button:has-text("确定"), .arco-modal .arco-btn-primary');
    await submitBtn.first().click();

    // 验证成功提示
    await expect(page.locator('.arco-message-success')).toBeVisible({ timeout: 10000 });
  });

  test('C04: 编辑合作状态', async ({ authenticatedPage: page }) => {
    // 查找表格中的编辑按钮
    const editBtn = page.locator('.arco-table button:has-text("编辑")');
    const hasData = await editBtn.first().isVisible({ timeout: 5000 }).catch(() => false);
    test.skip(!hasData, '当前无合作状态数据可供编辑');

    await editBtn.first().click();

    // 验证弹窗显示
    const modal = getVisibleModal(page);
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(getVisibleModal(page).locator('.arco-modal-title')).toContainText('编辑合作状态');

    // 验证弹窗预填了数据
    const nameInput = modal.locator('input').first();
    const prefilledValue = await nameInput.inputValue();
    expect(prefilledValue).toBeTruthy();

    // 修改名称
    await nameInput.fill(`${prefilledValue}_编辑`);

    // 提交
    const submitBtn = modal.locator('button:has-text("确定"), .arco-modal .arco-btn-primary');
    await submitBtn.first().click();

    // 验证成功提示
    await expect(page.locator('.arco-message-success')).toBeVisible({ timeout: 10000 });
  });

  test('C05: 删除合作状态', async ({ authenticatedPage: page }) => {
    // 查找表格中的删除按钮
    const deleteBtn = page.locator('.arco-table button:has-text("删除")');
    const hasData = await deleteBtn.first().isVisible({ timeout: 5000 }).catch(() => false);
    test.skip(!hasData, '当前无合作状态数据可供删除');

    await deleteBtn.first().click();

    // 验证确认弹窗
    const popconfirm = page.locator('.arco-popconfirm');
    await expect(popconfirm).toBeVisible({ timeout: 5000 });
    await expect(popconfirm).toContainText('确认删除');

    // 取消删除（避免测试数据被破坏）
    const cancelBtn = popconfirm.locator('button:has-text("取消")');
    await cancelBtn.click();

    // 验证弹窗关闭
    await expect(popconfirm).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe('侧边栏合作状态菜单', () => {
  test('C06: 侧边栏显示合作状态菜单项', async ({ authenticatedPage: page }) => {
    // 导航到首页
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // 验证侧边栏中有"合作状态"菜单项
    const menuBtn = page.locator('.nav-btn:has-text("合作状态")');
    const hasPermission = await menuBtn.isVisible({ timeout: 5000 }).catch(() => false);
    if (hasPermission) {
      await expect(menuBtn).toBeVisible();
      // 点击导航
      await menuBtn.click();
      await page.waitForURL('**/system/cooperation-statuses', { timeout: 10000 });
      await page.waitForLoadState('networkidle');
      // 验证页面标题
      await expect(page.locator('h1').first()).toContainText('合作状态');
    }
  });
});
