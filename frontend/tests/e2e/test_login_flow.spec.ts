import { test, expect } from './fixtures';

/**
 * 登录流程 E2E 测试
 */
test.describe('登录流程', () => {
  test('成功登录', async ({ loginPage, page }) => {
    // Arco Design 使用 field 属性
    await loginPage.fill('input[field="username"], input[type="text"]', 'admin');
    await loginPage.fill('input[field="password"], input[type="password"]', 'admin123');
    await loginPage.click('button[type="submit"], button:has-text("登录")');
    
    await expect(loginPage).toHaveURL('/');
    // 等待首页加载 - 使用更具体的选择器
    await page.waitForTimeout(1000);
    // 检查用户信息或菜单存在即可
    const userInfo = page.locator('.user-info, [class*="user-info"]');
    await expect(userInfo.first()).toBeVisible();
  });

  test('密码错误提示', async ({ loginPage, page }) => {
    await loginPage.fill('input[field="username"], input[type="text"]', 'admin');
    await loginPage.fill('input[field="password"], input[type="password"]', 'wrongpassword');
    await loginPage.click('button[type="submit"], button:has-text("登录")');
    
    // 等待错误消息
    await page.waitForTimeout(500);
    await expect(loginPage.locator('.arco-message-error, [class*="error"], :has-text("密码错误")')).toBeVisible();
    await expect(loginPage).toHaveURL('/login');
  });

  test('未登录访问受保护页面', async ({ page }) => {
    await page.goto('/customers');
    
    // 应该重定向到登录页
    await expect(page).toHaveURL('/login');
  });

  test('已登录访问登录页重定向', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/login');
    
    // 应该重定向到首页
    await expect(authenticatedPage).toHaveURL('/');
  });
});
