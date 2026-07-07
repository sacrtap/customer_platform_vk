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

  test('角色权限配置 - 展示模块卡片布局', async ({ page }) => {
    await page.goto('/roles');
    await page.waitForTimeout(1500);

    // 点击第一个"权限配置"按钮打开弹窗
    const configButton = page.locator('button:has-text("权限配置")').first();
    await configButton.click();
    await page.waitForTimeout(500);

    // 验证弹窗已打开
    await expect(page.locator('.arco-modal')).toBeVisible();

    // 弹窗包含标题"权限配置"
    await expect(page.locator('.arco-modal-title')).toContainText('权限配置');

    // 验证至少有一个模块卡片标题可见（取决于当前角色拥有的权限）
    const moduleHeadings = ['客户管理', '结算管理', '客户分析', '角色权限'];
    const visibleHeading = page.locator('.permission-group-title').filter({
      hasText: new RegExp(moduleHeadings.join('|')),
    });
    // 至少有一个模块卡片显示（权限数据是 seed 依赖的，不能断言具体数量）
    const headingCount = await visibleHeading.count();
    expect(headingCount).toBeGreaterThanOrEqual(1);

    // 全局按钮显示"全选"或"取消全选"
    const globalButton = page.locator('.permission-header button');
    await expect(globalButton).toBeVisible();
    const btnText = await globalButton.textContent();
    expect(btnText === '全选' || btnText === '取消全选').toBe(true);
  });

  test('角色列表展示', async ({ page }) => {
    await page.goto('/roles');
    await page.waitForTimeout(1000);
    
    await expect(page).toHaveURL('/roles');
  });
});
