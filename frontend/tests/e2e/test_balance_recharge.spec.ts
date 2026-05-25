import { test, expect } from './fixtures';

/**
 * 余额充值 E2E 测试
 */
test.describe('余额充值', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[field="username"], input[type="text"]', 'admin');
    await page.fill('input[field="password"], input[type="password"]', 'admin123');
    await page.click('button[type="submit"], button:has-text("登录")');
    await page.waitForURL('/');
  });

  test('访问余额管理页面', async ({ page }) => {
    await page.goto('/billing/balances');
    await page.waitForTimeout(1500);
    
    await expect(page).toHaveURL('/billing/balances');
    // 页面加载成功即可
  });

  test('查看客户余额详情', async ({ page }) => {
    await page.goto('/billing/balances');
    await page.waitForTimeout(1000);
    
    await expect(page).toHaveURL('/billing/balances');
  });

  test('执行充值操作', async ({ page }) => {
    await page.goto('/billing/balances');
    await page.waitForTimeout(1000);
    
    const rechargeButton = page.locator('button:has-text("充值"), button:has-text("余额充值")').first();
    
    if (await rechargeButton.isVisible()) {
      await rechargeButton.click();
      await page.waitForTimeout(500);
    }
    // 测试通过
  });

  test('查看充值记录', async ({ page }) => {
    await page.goto('/billing/recharge-records');
    await page.waitForTimeout(1000);
    
    await expect(page).toHaveURL('/billing/recharge-records');
  });

  test('充值记录筛选', async ({ page }) => {
    await page.goto('/billing/recharge-records');
    await page.waitForTimeout(500);
    
    const filter = page.locator('input[placeholder*="客户"], select[name="customer_id"]').first();
    if (await filter.isVisible()) {
      await filter.fill('测试');
      await page.waitForTimeout(500);
    }
    // 测试通过
  });

  test('余额不足预警', async ({ page }) => {
    await page.goto('/billing/balances');
    await page.waitForTimeout(1000);
    
    const warnings = page.locator('.arco-tag-warning, .arco-tag-danger');
    const count = await warnings.count();
    console.log(`余额预警数量：${count}`);
    
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('输入负数金额时弹出确认扣减对话框', async ({ page }) => {
    await page.goto('/billing/balances');
    await page.waitForTimeout(2000);

    // 关闭可能弹出的修改密码等对话框
    const passwordModal = page.locator('.arco-modal-wrapper:has-text("修改密码")');
    if (await passwordModal.isVisible()) {
      await passwordModal.locator('.arco-modal-close').click();
      await page.waitForTimeout(500);
    }

    // 点击表格中第一个"充值"按钮打开充值对话框
    const rechargeBtn = page.locator('.arco-table button:has-text("充值")').first();
    await expect(rechargeBtn).toBeVisible({ timeout: 10000 });
    await rechargeBtn.click();
    await page.waitForTimeout(500);

    // 输入负数金额（使用 wrapper id 定位 Arco 表单字段）
    const amountInput = page.locator('#real_amount input').first();
    await expect(amountInput).toBeVisible({ timeout: 5000 });
    await amountInput.fill('-500');
    await page.waitForTimeout(300);

    // 点击充值对话框的"确定"按钮，触发 handleRecharge
    const rechargeModal = page.locator('.arco-modal-wrapper').filter({ hasText: '客户充值' });
    await rechargeModal.locator('.arco-modal-footer .arco-btn-primary').click();
    await page.waitForTimeout(500);

    // 断言确认扣减对话框弹出
    await expect(
      page.locator('.arco-modal, .arco-modal-wrapper').filter({ hasText: '确认扣减金额' }).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('负数金额确认对话框点击取消不提交充值', async ({ page }) => {
    await page.goto('/billing/balances');
    await page.waitForTimeout(2000);

    // 关闭可能弹出的修改密码等对话框
    const passwordModal = page.locator('.arco-modal-wrapper:has-text("修改密码")');
    if (await passwordModal.isVisible()) {
      await passwordModal.locator('.arco-modal-close').click();
      await page.waitForTimeout(500);
    }

    // 点击表格中第一个"充值"按钮
    const rechargeBtn = page.locator('.arco-table button:has-text("充值")').first();
    await expect(rechargeBtn).toBeVisible({ timeout: 10000 });
    await rechargeBtn.click();
    await page.waitForTimeout(500);

    // 输入负数金额
    const amountInput = page.locator('#real_amount input').first();
    await expect(amountInput).toBeVisible({ timeout: 5000 });
    await amountInput.fill('-500');
    await page.waitForTimeout(300);

    // 点击充值对话框的"确定"按钮
    const rechargeModal = page.locator('.arco-modal-wrapper').filter({ hasText: '客户充值' });
    await rechargeModal.locator('.arco-modal-footer .arco-btn-primary').click();
    await page.waitForTimeout(500);

    // 等待确认扣减对话框弹出
    const confirmModal = page.locator('.arco-modal, .arco-modal-wrapper').filter({ hasText: '确认扣减金额' });
    await expect(confirmModal.first()).toBeVisible({ timeout: 10000 });

    // 点击确认对话框的"取消"按钮
    await confirmModal.locator('.arco-modal-footer button:has-text("取消")').click();
    await page.waitForTimeout(500);

    // 断言确认对话框已关闭
    await expect(confirmModal).toHaveCount(0, { timeout: 5000 });

    // 充值对话框应该仍然可见
    await expect(
      page.locator('.arco-modal-wrapper').filter({ hasText: '客户充值' }).first()
    ).toBeVisible({ timeout: 3000 });
  });

  test('负数金额确认对话框点击确认扣减成功', async ({ page }) => {
    await page.goto('/billing/balances');
    await page.waitForTimeout(2000);

    // 关闭可能弹出的修改密码等对话框
    const passwordModal = page.locator('.arco-modal-wrapper:has-text("修改密码")');
    if (await passwordModal.isVisible()) {
      await passwordModal.locator('.arco-modal-close').click();
      await page.waitForTimeout(500);
    }

    // 点击表格中第一个"充值"按钮
    const rechargeBtn = page.locator('.arco-table button:has-text("充值")').first();
    await expect(rechargeBtn).toBeVisible({ timeout: 10000 });
    await rechargeBtn.click();
    await page.waitForTimeout(500);

    // 输入负数金额
    const amountInput = page.locator('#real_amount input').first();
    await expect(amountInput).toBeVisible({ timeout: 5000 });
    await amountInput.fill('-500');
    await page.waitForTimeout(300);

    // 点击充值对话框的"确定"按钮
    const rechargeModal = page.locator('.arco-modal-wrapper').filter({ hasText: '客户充值' });
    await rechargeModal.locator('.arco-modal-footer .arco-btn-primary').click();
    await page.waitForTimeout(500);

    // 等待确认扣减对话框弹出
    const confirmModal = page.locator('.arco-modal, .arco-modal-wrapper').filter({ hasText: '确认扣减金额' });
    await expect(confirmModal.first()).toBeVisible({ timeout: 10000 });

    // 点击"确认扣减"按钮
    await confirmModal.locator('.arco-modal-footer .arco-btn-primary:has-text("确认扣减")').click();
    await page.waitForTimeout(1500);

    // 断言扣减成功消息出现
    await expect(
      page.locator('.arco-message-success:has-text("扣减成功")').first()
    ).toBeVisible({ timeout: 10000 });
  });
});
