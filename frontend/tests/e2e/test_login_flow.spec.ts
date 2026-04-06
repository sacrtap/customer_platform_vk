import { test, expect } from './fixtures';

/**
 * 登录流程 E2E 测试
 * 覆盖场景：
 * 1. 成功登录并跳转到首页
 * 2. 密码错误显示错误提示
 * 3. 用户不存在显示错误提示
 * 4. 未登录访问受保护页面重定向到登录页
 */
test.describe('登录流程', () => {
  test('成功登录并跳转到首页', async ({ loginPage, page }) => {
    await loginPage.fill('input[field="username"], input[type="text"]', 'admin');
    await loginPage.fill('input[field="password"], input[type="password"]', 'admin123');
    await loginPage.click('button[type="submit"], button:has-text("登录")');
    
    await expect(loginPage).toHaveURL('/');
    const userInfo = page.locator('.user-info, [class*="user-info"]');
    await expect(userInfo.first()).toBeVisible();
  });

  test('密码错误显示错误提示', async ({ loginPage, page }) => {
    await loginPage.fill('input[field="username"], input[type="text"]', 'admin');
    await loginPage.fill('input[field="password"], input[type="password"]', 'wrongpassword');
    await loginPage.click('button[type="submit"], button:has-text("登录")');
    
    await page.waitForTimeout(500);
    await expect(loginPage.locator('.arco-message-error, :has-text("密码错误"), :has-text("登录失败")')).toBeVisible();
    await expect(loginPage).toHaveURL('/login');
  });

  test('用户不存在显示错误提示', async ({ loginPage, page }) => {
    await loginPage.fill('input[field="username"], input[type="text"]', 'nonexistent_user_12345');
    await loginPage.fill('input[field="password"], input[type="password"]', 'somepassword');
    await loginPage.click('button[type="submit"], button:has-text("登录")');
    
    await page.waitForTimeout(500);
    await expect(loginPage.locator('.arco-message-error, :has-text("用户不存在"), :has-text("登录失败")')).toBeVisible();
    await expect(loginPage).toHaveURL('/login');
  });

  test('未登录访问受保护页面重定向到登录页', async ({ page }) => {
    await page.goto('/customers');
    await expect(page).toHaveURL('/login');
  });
});
