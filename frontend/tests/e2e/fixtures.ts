import { test as base, expect, type Page } from '@playwright/test';

/**
 * Playwright 测试夹具
 * 
 * 提供预配置的测试页面和认证状态
 */

// 扩展测试夹具
export const test = base.extend<{
  loginPage: Page;
  authenticatedPage: Page;
}>({
  loginPage: async ({ page }, use) => {
    // 导航到登录页，使用 domcontentloaded 减少等待时间
    await page.goto('/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
    // 等待登录表单加载
    await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
    await use(page);
  },
  
  authenticatedPage: async ({ page }, use) => {
    // 登录
    await page.goto('/login');
    // 等待登录表单加载
    await page.waitForSelector('input[field="username"], input[type="text"]');
    // Arco Design 输入框使用 field 属性而不是 name
    await page.fill('input[field="username"], input[type="text"]', 'admin');
    await page.fill('input[field="password"], input[type="password"]', 'admin123');
    await page.click('button[type="submit"], button:has-text("登录")');
    // 增加超时时间到 60s，等待登录成功跳转
    await page.waitForURL('/', { timeout: 60000, waitUntil: 'domcontentloaded' });
    // 额外等待确保页面完全加载
    await page.waitForTimeout(1000);
    await use(page);
  },
});

export { expect };
