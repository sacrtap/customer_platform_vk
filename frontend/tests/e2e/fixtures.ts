import { test as base, expect } from '@playwright/test';

/**
 * Playwright 测试夹具
 * 
 * 提供预配置的测试页面和认证状态
 */

// 扩展测试夹具
export const test = base.extend<{
  loginPage: any;
  authenticatedPage: any;
}>({
  loginPage: async ({ page }, use) => {
    // 导航到登录页
    await page.goto('/login');
    await use(page);
  },
  
  authenticatedPage: async ({ page }, use) => {
    // 登录
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/');
    await use(page);
  },
});

export { expect };
