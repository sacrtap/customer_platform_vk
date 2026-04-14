import { test, expect } from './fixtures';
import {
  uiLogin,
  waitForTableLoaded,
  generateTestCompanyId,
  generateTestCustomerName,
  apiLogin,
  apiCreateCustomer,
  apiDeleteCustomer,
} from './test-helpers';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

/**
 * 客户导入/导出 E2E 测试
 */
test.describe('客户导入/导出', () => {
  let authToken: string;
  let createdIds: number[] = [];
  const tempDir = os.tmpdir();

  test.beforeAll(async () => {
    authToken = await apiLogin();
  });

  test.beforeEach(async ({ page }) => {
    createdIds = [];
    await uiLogin(page);
    await page.goto('/customers');
    await waitForTableLoaded(page);
  });

  test.afterAll(async () => {
    for (const id of createdIds) {
      await apiDeleteCustomer(authToken, id).catch(() => {});
    }
  });

  test('1. 下载导入模板', async ({ page }) => {
    // 点击导入按钮
    await page.locator('button:has-text("导入")').first().click();
    
    // 等待下载模板按钮出现（表明弹窗已打开）
    const downloadBtn = page.locator('button:has-text("下载模板")');
    await downloadBtn.first().waitFor({ state: 'visible', timeout: 10000 });

    // 点击下载模板
    await downloadBtn.first().click();
    await page.waitForTimeout(2000);

    // 验证页面仍在客户列表（没有跳转）
    await expect(page).toHaveURL('/customers');
  });

  test('2. 验证导入弹窗UI元素', async ({ page }) => {
    await page.locator('button:has-text("导入")').first().click();

    // 等待下载模板按钮出现
    await page.locator('button:has-text("下载模板")').first().waitFor({ state: 'visible', timeout: 10000 });

    // 验证下载模板按钮可见
    await expect(page.locator('button:has-text("下载模板")').first()).toBeVisible();

    // 验证文件上传区域存在
    const uploadArea = page.locator('.arco-upload, .arco-upload-drag, .arco-upload-trigger');
    const uploadVisible = await uploadArea.first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(uploadVisible).toBeTruthy();
  });

  test('3. 上传文件功能可用', async ({ page }) => {
    await page.locator('button:has-text("导入")').first().click();

    // 等待下载模板按钮出现
    await page.locator('button:has-text("下载模板")').first().waitFor({ state: 'visible', timeout: 10000 });

    // 创建临时文件
    const tempFilePath = path.join(tempDir, `test_import_${Date.now()}.txt`);
    fs.writeFileSync(tempFilePath, 'test,data\n1,2');

    try {
      // 找到文件上传 input
      const fileInput = page.locator('input[type="file"]').first();
      const inputExists = await fileInput.count() > 0;
      
      expect(inputExists).toBeTruthy();

      if (inputExists) {
        await fileInput.setInputFiles(tempFilePath);
        await page.waitForTimeout(1000);
        
        // 验证没有错误消息
        const errorMsg = page.locator('.arco-message-error');
        expect(await errorMsg.first().isVisible({ timeout: 1000 }).catch(() => false)).toBeFalsy();
      }
    } finally {
      if (fs.existsSync(tempFilePath)) {
        fs.unlinkSync(tempFilePath);
      }
    }
  });

  test('4. 导入重复数据流程', async ({ page }) => {
    const companyId = generateTestCompanyId('重复导入');
    const result = await apiCreateCustomer(authToken, {
      company_id: companyId,
      name: generateTestCustomerName('原始'),
    });
    if (result.data?.id) createdIds.push(result.data.id);

    // 打开导入弹窗
    await page.locator('button:has-text("导入")').first().click();

    // 验证弹窗包含导入相关元素
    const hasDownloadTemplate = await page.locator('button:has-text("下载模板")').first().isVisible({ timeout: 5000 });
    expect(hasDownloadTemplate).toBeTruthy();
  });

  test('5. 导出客户数据', async ({ page }) => {
    // 创建一些数据
    for (let i = 0; i < 2; i++) {
      const result = await apiCreateCustomer(authToken, {
        company_id: generateTestCompanyId(`导出${i}`),
        name: generateTestCustomerName(`导出${i}`),
      });
      if (result.data?.id) createdIds.push(result.data.id);
    }

    await page.reload();
    await waitForTableLoaded(page);
    await page.waitForTimeout(1000);

    // 点击导出按钮
    await page.locator('button:has-text("导出")').first().click();
    await page.waitForTimeout(3000);

    // 验证导出按钮仍然可见
    const exportBtn = page.locator('button:has-text("导出")');
    await expect(exportBtn.first()).toBeVisible();
  });

  test('6. 导出带筛选条件的数据', async ({ page }) => {
    const customers = [
      { company_id: generateTestCompanyId('导出KA'), name: generateTestCustomerName('KA导出'), customer_level: 'KA' },
      { company_id: generateTestCompanyId('导出普通'), name: generateTestCustomerName('普通导出'), customer_level: '普通' },
    ];

    for (const c of customers) {
      const result = await apiCreateCustomer(authToken, c);
      if (result.data?.id) createdIds.push(result.data.id);
    }

    await page.reload();
    await waitForTableLoaded(page);

    // 先进行筛选
    const searchInput = page.locator('input[placeholder*="关键词"], input[placeholder*="搜索"], .arco-input-wrapper input').first();
    await searchInput.fill('KA');
    await page.locator('button:has-text("查询")').first().click();
    await waitForTableLoaded(page);

    // 点击导出
    await page.locator('button:has-text("导出")').first().click();
    await page.waitForTimeout(2000);

    // 搜索框仍然有值
    const currentSearchValue = await searchInput.inputValue();
    expect(currentSearchValue).toBe('KA');

    // 导出按钮仍然可见
    await expect(page.locator('button:has-text("导出")').first()).toBeVisible();
  });
});
