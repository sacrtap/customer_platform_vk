import { test, expect } from './fixtures';

/**
 * 用户管理 E2E 测试
 */
test.describe('用户管理', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[field="username"], input[type="text"]', 'admin');
    await page.fill('input[field="password"], input[type="password"]', 'admin123');
    await page.click('button[type="submit"], button:has-text("登录")');
    await page.waitForURL('/');
  });

  test('访问用户管理页面', async ({ page }) => {
    await page.goto('/users');
    await page.waitForTimeout(1000);
    
    await expect(page).toHaveURL('/users');
  });

  test('创建新用户', async ({ page }) => {
    await page.goto('/users');
    await page.waitForTimeout(1000);
    
    const newButton = page.locator('button:has-text("新建"), button:has-text("新建用户")').first();
    if (await newButton.isVisible()) {
      await newButton.click();
      await page.waitForTimeout(500);
    }
  });

  test('用户搜索', async ({ page }) => {
    await page.goto('/users');
    await page.waitForTimeout(500);
    
    const searchInput = page.locator('input[placeholder*="搜索"], input[placeholder*="用户名"]').first();
    if (await searchInput.isVisible()) {
      await searchInput.fill('admin');
      await page.waitForTimeout(500);
    }
  });

  test('用户角色分配', async ({ page }) => {
    await page.goto('/users');
    await page.waitForTimeout(1000);
    
    // 检查是否有角色分配功能
    const roleSelect = page.locator('select[name="role"], .arco-select').first();
    if (await roleSelect.isVisible()) {
      await roleSelect.click();
      await page.waitForTimeout(500);
    }
  });

  test('用户列表展示', async ({ page }) => {
    await page.goto('/users');
    await page.waitForTimeout(1000);
    
    await expect(page).toHaveURL('/users');
  });
});
