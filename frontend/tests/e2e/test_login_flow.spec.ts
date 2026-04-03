import { test, expect } from './fixtures';

/**
 * 登录流程 E2E 测试
 */
test.describe('登录流程', () => {
  test('成功登录', async ({ loginPage }) => {
    await loginPage.fill('input[name="username"]', 'admin');
    await loginPage.fill('input[name="password"]', 'admin123');
    await loginPage.click('button[type="submit"]');
    
    await expect(loginPage).toHaveURL('/');
    await expect(loginPage.locator('.user-menu')).toBeVisible();
  });

  test('密码错误提示', async ({ loginPage }) => {
    await loginPage.fill('input[name="username"]', 'admin');
    await loginPage.fill('input[name="password"]', 'wrongpassword');
    await loginPage.click('button[type="submit"]');
    
    await expect(loginPage.locator('.arco-message-error')).toBeVisible();
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
