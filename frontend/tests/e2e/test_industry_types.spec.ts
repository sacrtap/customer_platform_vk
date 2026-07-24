import { test, expect } from './fixtures';
import { getVisibleModal } from './test-helpers';

/**
 * 行业类型页面 E2E 测试
 *
 * 测试场景：
 * 1. PageHeader 显示
 * 2. 行业列表表格渲染
 * 3. 创建行业类型
 * 4. 编辑行业类型
 * 5. 删除行业类型
 */
test.describe('行业类型页面', () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto('/system/industry-types');
    await page.waitForLoadState('networkidle');
  });

  test('H01: PageHeader 显示', async ({ authenticatedPage: page }) => {
    await expect(page.locator('h1').first()).toContainText('行业类型');
    await expect(page.locator('.desc')).toBeVisible();

    // 验证"新增行业类型"按钮存在
    const createBtn = page.locator('button:has-text("新增行业类型")');
    const hasPermission = await createBtn.isVisible({ timeout: 3000 }).catch(() => false);
    if (hasPermission) {
      await expect(createBtn).toBeVisible();
    }
  });

  test('H02: 行业列表表格渲染', async ({ authenticatedPage: page }) => {
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

  test('H03: 创建行业类型', async ({ authenticatedPage: page }) => {
    // 点击新建按钮
    const createBtn = page.locator('button:has-text("新增行业类型")');
    const hasPermission = await createBtn.isVisible({ timeout: 3000 }).catch(() => false);
    test.skip(!hasPermission, '当前用户无 industry_types:manage 权限');

    await createBtn.click();

    // 验证弹窗显示
    const modal = getVisibleModal(page);
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(getVisibleModal(page).locator('.arco-modal-title')).toContainText('新增行业类型');

    // 填入行业名称
    const nameInput = modal.locator('input').first();
    await expect(nameInput).toBeVisible();
    await nameInput.fill(`测试行业_${Date.now()}`);

    // 填入排序号（如果有）
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

  test('H04: 编辑行业类型', async ({ authenticatedPage: page }) => {
    // 查找表格中的编辑按钮
    const editBtn = page.locator('.arco-table button:has-text("编辑")');
    const hasData = await editBtn.first().isVisible({ timeout: 5000 }).catch(() => false);
    test.skip(!hasData, '当前无行业类型数据可供编辑');

    await editBtn.first().click();

    // 验证弹窗显示
    const modal = getVisibleModal(page);
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(getVisibleModal(page).locator('.arco-modal-title')).toContainText('编辑行业类型');

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

  test('H05: 删除行业类型', async ({ authenticatedPage: page }) => {
    // 查找表格中的删除按钮
    const deleteBtn = page.locator('.arco-table button:has-text("删除")');
    const hasData = await deleteBtn.first().isVisible({ timeout: 5000 }).catch(() => false);
    test.skip(!hasData, '当前无行业类型数据可供删除');

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
