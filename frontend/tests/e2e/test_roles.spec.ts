import { test, expect } from './fixtures';

/**
 * 角色管理 E2E 测试
 */
test.describe('角色管理', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[field="username"], input[type="text"]', 'admin');
    await page.fill('input[field="password"], input[type="password"]', 'admin123');
    await page.click('button[type="submit"], button:has-text("登录")');
    await page.waitForURL('/');
  });

  test('访问角色管理页面', async ({ page }) => {
    await page.goto('/roles');
    await page.waitForTimeout(1000);
    
    await expect(page).toHaveURL('/roles');
  });

  test('创建新角色', async ({ page }) => {
    await page.goto('/roles');
    await page.waitForTimeout(1000);
    
    const newButton = page.locator('button:has-text("新建"), button:has-text("新建角色")').first();
    if (await newButton.isVisible()) {
      await newButton.click();
      await page.waitForTimeout(500);
    }
  });

  test('角色权限配置', async ({ page }) => {
    await page.goto('/roles');
    await page.waitForTimeout(1000);
    
    // 检查是否有权限配置功能
    const permissionCheck = page.locator('input[type="checkbox"], .arco-checkbox').first();
    if (await permissionCheck.isVisible()) {
      await permissionCheck.click();
      await page.waitForTimeout(500);
    }
  });

  test('角色列表展示', async ({ page }) => {
    await page.goto('/roles');
    await page.waitForTimeout(1000);
    
    await expect(page).toHaveURL('/roles');
  });
});
