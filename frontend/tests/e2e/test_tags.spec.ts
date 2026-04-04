import { test, expect } from './fixtures';

/**
 * 标签管理 E2E 测试
 */
test.describe('标签管理', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[field="username"], input[type="text"]', 'admin');
    await page.fill('input[field="password"], input[type="password"]', 'admin123');
    await page.click('button[type="submit"], button:has-text("登录")');
    await page.waitForURL('/');
  });

  test('访问标签管理页面', async ({ page }) => {
    await page.goto('/tags');
    await page.waitForTimeout(1000);
    
    await expect(page).toHaveURL('/tags');
  });

  test('创建新标签', async ({ page }) => {
    await page.goto('/tags');
    await page.waitForTimeout(1000);
    
    const newButton = page.locator('button:has-text("新建"), button:has-text("新建标签")').first();
    if (await newButton.isVisible()) {
      await newButton.click();
      await page.waitForTimeout(500);
    }
  });

  test('标签分类筛选', async ({ page }) => {
    await page.goto('/tags');
    await page.waitForTimeout(500);
    
    const filter = page.locator('select[name="category"], .arco-select').first();
    if (await filter.isVisible()) {
      await filter.click();
      await page.waitForTimeout(500);
    }
  });

  test('标签搜索', async ({ page }) => {
    await page.goto('/tags');
    await page.waitForTimeout(500);
    
    const searchInput = page.locator('input[placeholder*="搜索"], input[placeholder*="标签名称"]').first();
    if (await searchInput.isVisible()) {
      await searchInput.fill('测试');
      await page.waitForTimeout(500);
    }
  });

  test('标签列表展示', async ({ page }) => {
    await page.goto('/tags');
    await page.waitForTimeout(1000);
    
    await expect(page).toHaveURL('/tags');
  });
});
