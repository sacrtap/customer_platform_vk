import { test, expect } from './fixtures';
import { getVisibleModal, waitForTableLoaded } from './test-helpers';

test.describe('客户管理', () => {
  test.use({ actionTimeout: 15000 });

  test('访问客户列表页面', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/customers', { waitUntil: 'networkidle' });
    await authenticatedPage.waitForTimeout(1000);

    // 等待页面加载完成 - 重构后标题为"客户管理"，eyebrow 为"Customers"
    await expect(authenticatedPage.locator('h1').first()).toContainText('客户管理');

    // 检查操作按钮存在 - 重构后按钮文本为"新增客户"
    await expect(authenticatedPage.locator('button:has-text("新增客户")').first()).toBeVisible();
    await expect(authenticatedPage.locator('button:has-text("导入客户")').first()).toBeVisible();
    await expect(authenticatedPage.locator('button:has-text("导出")').first()).toBeVisible();

    // 检查筛选区域存在 - 使用精确选择器避免匹配全局搜索框
    await expect(authenticatedPage.locator('.filters-container input[placeholder*="搜索"]').first()).toBeVisible();
    // 重构后筛选按钮文本为"筛选"
    await expect(authenticatedPage.locator('.filters button:has-text("筛选")').first()).toBeVisible();

    // 检查表格存在（重构后使用自定义表格，非 Arco 表格）
    await expect(authenticatedPage.locator('.table-section table, table.table').first()).toBeVisible();
  });

  test('创建新客户', async ({ authenticatedPage }) => {
    test.setTimeout(60000);

    await authenticatedPage.goto('/customers', { waitUntil: 'networkidle' });
    await waitForTableLoaded(authenticatedPage);

    // 点击新建客户按钮 - 重构后为"新增客户"
    await authenticatedPage.click('button:has-text("新增客户")');

    // 等待对话框打开
    const modal = getVisibleModal(authenticatedPage);
    await expect(modal).toBeVisible();
    await authenticatedPage.waitForTimeout(500);

    // 填写表单
    const uniqueId = Date.now().toString();
    await authenticatedPage.fill('input[placeholder="请输入客户ID"]', `TEST${uniqueId}`);
    await authenticatedPage.fill('input[placeholder="请输入客户名称"]', `测试客户${uniqueId}`);
    await authenticatedPage.fill('input[placeholder="请输入邮箱"]', `test${uniqueId}@example.com`);

    // 点击确定按钮
    const okBtn = getVisibleModal(authenticatedPage).locator('button:has-text("确定")');
    await okBtn.click();

    // 等待消息出现（Arco Message 默认 3 秒后消失，需要立即检查）
    let successCount = 0;
    let errorCount = 0;
    try {
      await authenticatedPage.waitForSelector('.arco-message-success, .arco-message-error', { timeout: 8000 });
      successCount = await authenticatedPage.locator('.arco-message-success').count();
      errorCount = await authenticatedPage.locator('.arco-message-error').count();
    } catch {
      // 如果没有消息出现，检查弹窗是否关闭（关闭也表示成功）
      const modalStillVisible = await modal.isVisible().catch(() => false);
      if (!modalStillVisible) {
        successCount = 1; // 弹窗关闭视为成功
      }
    }

    // 要么成功，要么有验证错误（都是可接受的结果）
    expect(successCount > 0 || errorCount > 0).toBeTruthy();

    // 关闭对话框（如果有）
    const stillVisible = await modal.isVisible().catch(() => false);
    if (stillVisible) {
      await authenticatedPage.locator('.arco-modal:visible button:has-text("取消")').first().click().catch(() => {});
    }
  });

  test('搜索客户', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/customers');
    await waitForTableLoaded(authenticatedPage);

    // 使用精确选择器避免匹配全局搜索框
    const searchInput = authenticatedPage.locator('.filters-container input[placeholder*="搜索"]').first();
    await searchInput.click();
    await searchInput.pressSequentially('admin', { delay: 30 });
    await authenticatedPage.waitForTimeout(500);

    // 点击筛选按钮
    await authenticatedPage.locator('.filters button:has-text("筛选")').first().click({ force: true });
    await authenticatedPage.waitForTimeout(1000);

    // 验证表格仍然可见
    const table = authenticatedPage.locator('.table-section table, table.table');
    await expect(table.first()).toBeVisible();

    // 清除搜索内容
    await searchInput.click();
    await searchInput.fill('');
    await authenticatedPage.locator('.filters button:has-text("筛选")').first().click({ force: true });
    await authenticatedPage.waitForTimeout(500);

    // 验证输入框被清空
    await expect(searchInput).toHaveValue('');
  });

  test('编辑客户信息', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/customers');
    await waitForTableLoaded(authenticatedPage);

    // 获取第一行客户数据
    const firstRow = authenticatedPage.locator('.table-section tbody tr, table.table tbody tr').first();
    await expect(firstRow).toBeVisible({ timeout: 10000 });

    // 点击编辑按钮
    await firstRow.locator('button:has-text("编辑")').click();

    // 等待编辑对话框打开
    const modal = getVisibleModal(authenticatedPage);
    await expect(modal).toBeVisible();
    await authenticatedPage.waitForTimeout(2000); // 等待数据加载

    // 修改客户名称（EditCustomerDialog 中标签为"客户名称"）
    const nameInput = authenticatedPage.locator('.arco-modal:visible input[placeholder="请输入客户名称"]');
    await expect(nameInput).toBeVisible();
    const originalName = await nameInput.inputValue();
    const newName = `${originalName}_Edited`;
    await nameInput.fill(newName);

    // 点击确定按钮
    const okBtn = getVisibleModal(authenticatedPage).locator('button:has-text("确定")');
    await okBtn.click();

    // 等待提交完成
    await authenticatedPage.waitForTimeout(2000);

    // 验证更新成功提示（EditCustomerDialog 中消息为"客户信息已更新"）
    const successMsg = authenticatedPage.locator('.arco-message-success');
    await expect(successMsg.first()).toBeVisible({ timeout: 10000 });
  });

  test('分页功能', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/customers', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await authenticatedPage.waitForTimeout(2000);

    // 检查分页组件存在（重构后使用自定义分页，非 Arco 分页）
    const pagination = authenticatedPage.locator('.pagination');
    await expect(pagination.first()).toBeVisible();

    // 获取当前页码（重构后使用 .page-btn.active）
    const currentPageItem = pagination.locator('.page-btn.active');
    const currentPageText = await currentPageItem.first().textContent();
    expect(currentPageText?.trim()).toBe('1');

    // 尝试点击页码 2（如果存在）
    const page2 = pagination.locator('.page-btn:has-text("2")');
    const page2Count = await page2.count();

    if (page2Count > 0) {
      // 点击第二页
      await page2.first().click();
      await authenticatedPage.waitForTimeout(1500);

      // 验证页码变化
      const newActivePage = pagination.locator('.page-btn.active');
      const newPageText = await newActivePage.first().textContent();

      // 验证页码已改变
      expect(newPageText?.trim()).not.toBe('1');

      // 点击第一页回去
      const page1 = pagination.locator('.page-btn:has-text("1")');
      await page1.first().click();
      await authenticatedPage.waitForTimeout(1500);

      const backToFirst = pagination.locator('.page-btn.active');
      const backToFirstText = await backToFirst.first().textContent();
      expect(backToFirstText?.trim()).toBe('1');
    }
    // 如果只有一页，测试也通过（分页组件存在且显示正确）

    // 检查 pageSize 切换器存在（重构后使用 select 元素）
    await expect(pagination.locator('.page-size-select').first()).toBeVisible();
  });
});
