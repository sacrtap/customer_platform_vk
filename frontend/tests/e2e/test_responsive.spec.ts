import { test, expect } from './fixtures';

/**
 * 响应式断点测试
 *
 * 使用 page.setViewportSize 模拟不同屏幕宽度，
 * 验证 1100px / 960px / 640px 三个断点的布局行为。
 */
test.describe('响应式断点测试', () => {
  test.describe('≤ 1100px 断点', () => {
    test('J01: 侧边栏切为 fixed 定位', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 1100, height: 800 },
      });
      const page = await context.newPage();

      // 登录
      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
      await page.fill('input[field="username"], input[type="text"]', 'admin');
      await page.fill('input[field="password"], input[type="password"]', 'admin123');
      await page.click('button[type="submit"], button:has-text("登录")');
      await page.waitForURL('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      // 验证侧边栏 position: fixed
      const sidePosition = await page.evaluate(() => {
        const side = document.querySelector('.side');
        if (!side) return null;
        return getComputedStyle(side).position;
      });

      expect(sidePosition).toBe('fixed');
      await context.close();
    });

    test('J02: 侧边栏默认隐藏（translateX(-100%)）', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 1100, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
      await page.fill('input[field="username"], input[type="text"]', 'admin');
      await page.fill('input[field="password"], input[type="password"]', 'admin123');
      await page.click('button[type="submit"], button:has-text("登录")');
      await page.waitForURL('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      // 验证侧边栏 transform 包含 translateX
      const sideTransform = await page.evaluate(() => {
        const side = document.querySelector('.side');
        if (!side) return null;
        return getComputedStyle(side).transform;
      });

      expect(sideTransform).toContain('matrix');
      // transform 应包含负值（translateX(-100%)）
      expect(sideTransform).not.toBe('none');

      await context.close();
    });

    test('J03: 点击移动端菜单按钮 → 侧边栏滑出', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 1100, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
      await page.fill('input[field="username"], input[type="text"]', 'admin');
      await page.fill('input[field="password"], input[type="password"]', 'admin123');
      await page.click('button[type="submit"], button:has-text("登录")');
      await page.waitForURL('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      // 点击移动端菜单按钮
      const mobileMenuBtn = page.locator('.mobile-menu-btn');
      await expect(mobileMenuBtn).toBeVisible();
      await mobileMenuBtn.click();
      await page.waitForTimeout(300);

      // 验证侧边栏有 mobile-open 类
      const side = page.locator('.side');
      await expect(side).toHaveClass(/mobile-open/);

      await context.close();
    });

    test('J04: .grid-4/.grid-3/.grid-2 切为 1fr（单列）', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 1100, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
      await page.fill('input[field="username"], input[type="text"]', 'admin');
      await page.fill('input[field="password"], input[type="password"]', 'admin123');
      await page.click('button[type="submit"], button:has-text("登录")');
      await page.waitForURL('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      // 验证 .grid-4 使用单列
      const gridStyles = await page.evaluate(() => {
        const grid = document.querySelector('.grid-4');
        if (!grid) return null;
        return getComputedStyle(grid).gridTemplateColumns;
      });

      if (gridStyles) {
        expect(gridStyles).toBe('1fr');
      }

      await context.close();
    });

    test('J05: .desktop-only 元素隐藏', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 1100, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
      await page.fill('input[field="username"], input[type="text"]', 'admin');
      await page.fill('input[field="password"], input[type="password"]', 'admin123');
      await page.click('button[type="submit"], button:has-text("登录")');
      await page.waitForURL('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      // 验证 .desktop-only 元素隐藏
      const desktopOnly = page.locator('.desktop-only');
      const count = await desktopOnly.count();
      if (count > 0) {
        const display = await page.evaluate(() => {
          const el = document.querySelector('.desktop-only');
          if (!el) return null;
          return getComputedStyle(el).display;
        });
        expect(display).toBe('none');
      }

      await context.close();
    });

    test('J06: 移动端遮罩层显示', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 1100, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
      await page.fill('input[field="username"], input[type="text"]', 'admin');
      await page.fill('input[field="password"], input[type="password"]', 'admin123');
      await page.click('button[type="submit"], button:has-text("登录")');
      await page.waitForURL('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      // 点击移动菜单按钮打开侧边栏
      await page.locator('.mobile-menu-btn').click();
      await page.waitForTimeout(300);

      // 验证遮罩层显示
      const overlay = page.locator('.mobile-overlay');
      await expect(overlay).toBeVisible();

      await context.close();
    });
  });

  test.describe('≤ 960px 断点（登录页）', () => {
    test('J07: 登录页切单列布局', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 960, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });

      const loginShellStyles = await page.evaluate(() => {
        const shell = document.querySelector('.login-box');
        if (!shell) return null;
        const styles = getComputedStyle(shell);
        return {
          gridTemplateColumns: styles.gridTemplateColumns,
          maxWidth: styles.maxWidth,
        };
      });

      expect(loginShellStyles).not.toBeNull();
      // 应为单列布局
      const colCount = loginShellStyles!.gridTemplateColumns.split(' ').length;
      expect(colCount).toBe(1);
      expect(loginShellStyles!.maxWidth).toBe('520px');

      await context.close();
    });

    test('J08: 登录页品牌区+表单区垂直堆叠', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 960, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });

      // 验证品牌区和表单区都可见
      await expect(page.locator('.login-brand')).toBeVisible();
      await expect(page.locator('.login-form-panel')).toBeVisible();

      await context.close();
    });

    test('J09: 登录页第 3+ 特性项隐藏', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 960, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });

      // 验证第 3 个特性项隐藏
      const featureItems = page.locator('.feature-item');
      const count = await featureItems.count();

      if (count >= 3) {
        const thirdItemDisplay = await page.evaluate(() => {
          const items = document.querySelectorAll('.feature-item');
          if (items.length >= 3) {
            return getComputedStyle(items[2] as HTMLElement).display;
          }
          return null;
        });
        expect(thirdItemDisplay).toBe('none');
      }

      await context.close();
    });
  });

  test.describe('≤ 640px 断点', () => {
    test('J10: 登录页全屏无圆角', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 640, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });

      // 验证登录框存在并检查样式
      const loginBox = page.locator('.login-box');
      await expect(loginBox).toBeVisible({ timeout: 5000 });

      // 在小屏幕下 border-radius 应为 0px
      await expect(loginBox).toHaveCSS('border-radius', '0px');

      await context.close();
    });

    test('J11: 页面 padding 缩小至 16px', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 640, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
      await page.fill('input[field="username"], input[type="text"]', 'admin');
      await page.fill('input[field="password"], input[type="password"]', 'admin123');
      await page.click('button[type="submit"], button:has-text("登录")');
      await page.waitForURL('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      const pagePadding = await page.evaluate(() => {
        const pageEl = document.querySelector('.page');
        if (!pageEl) return null;
        return getComputedStyle(pageEl).padding;
      });

      expect(pagePadding).not.toBeNull();
      expect(pagePadding).toBe('16px');

      await context.close();
    });

    test('J12: 搜索框换行全宽', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 640, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
      await page.fill('input[field="username"], input[type="text"]', 'admin');
      await page.fill('input[field="password"], input[type="password"]', 'admin123');
      await page.click('button[type="submit"], button:has-text("登录")');
      await page.waitForURL('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      const searchStyles = await page.evaluate(() => {
        const search = document.querySelector('.search');
        if (!search) return null;
        const styles = getComputedStyle(search);
        return {
          flexBasis: styles.flexBasis,
          maxWidth: styles.maxWidth,
        };
      });

      expect(searchStyles).not.toBeNull();
      expect(searchStyles!.flexBasis).toBe('100%');

      await context.close();
    });

    test('J13: .kpi-strip 切为单列', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 640, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
      await page.fill('input[field="username"], input[type="text"]', 'admin');
      await page.fill('input[field="password"], input[type="password"]', 'admin123');
      await page.click('button[type="submit"], button:has-text("登录")');
      await page.waitForURL('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      const kpiStyles = await page.evaluate(() => {
        const kpi = document.querySelector('.kpi-strip');
        if (!kpi) return null;
        return getComputedStyle(kpi).gridTemplateColumns;
      });

      if (kpiStyles) {
        // getComputedStyle 会将 1fr 解析为像素值，检查列数是否为 1
        const colCount = kpiStyles.split(' ').length;
        expect(colCount).toBe(1);
      }

      await context.close();
    });

    test('J14: .nav-hint 元素隐藏', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 640, height: 800 },
      });
      const page = await context.newPage();

      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
      await page.fill('input[field="username"], input[type="text"]', 'admin');
      await page.fill('input[field="password"], input[type="password"]', 'admin123');
      await page.click('button[type="submit"], button:has-text("登录")');
      await page.waitForURL('/', { timeout: 60000 });
      await page.waitForLoadState('networkidle');

      const navHintDisplay = await page.evaluate(() => {
        const hint = document.querySelector('.nav-hint');
        if (!hint) return null;
        return getComputedStyle(hint).display;
      });

      if (navHintDisplay !== null) {
        expect(navHintDisplay).toBe('none');
      }

      await context.close();
    });
  });
});
