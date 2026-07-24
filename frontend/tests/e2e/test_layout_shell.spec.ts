import { test, expect } from './fixtures';

/**
 * 布局框架测试
 *
 * 验证 Dashboard Grid 布局、侧边栏交互、顶栏交互的核心行为。
 * 确保重构后的布局与原型设计规范一致。
 */
test.describe('布局框架', () => {
  test.describe('Dashboard Grid 布局', () => {
    test.beforeEach(async ({ authenticatedPage: page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    });

    test('C01: .shell 使用 grid 布局，grid-template-columns = 252px 1fr', async ({ authenticatedPage: page }) => {
      const shellStyles = await page.evaluate(() => {
        const shell = document.querySelector('.shell');
        if (!shell) return null;
        const styles = getComputedStyle(shell);
        return {
          display: styles.display,
          gridTemplateColumns: styles.gridTemplateColumns,
        };
      });

      expect(shellStyles).not.toBeNull();
      expect(shellStyles!.display).toBe('grid');
      expect(shellStyles!.gridTemplateColumns).toContain('252px');
    });

    test('C02: 折叠态 .shell.collapsed grid-template-columns = 72px 1fr', async ({ authenticatedPage: page }) => {
      // 点击折叠按钮
      const toggleBtn = page.locator('.toggle-btn');
      await expect(toggleBtn).toBeVisible();
      await toggleBtn.click();
      await page.waitForTimeout(500);

      const shellStyles = await page.evaluate(() => {
        const shell = document.querySelector('.shell');
        if (!shell) return null;
        const styles = getComputedStyle(shell);
        return {
          gridTemplateColumns: styles.gridTemplateColumns,
          classList: shell.classList.contains('collapsed'),
        };
      });

      expect(shellStyles).not.toBeNull();
      expect(shellStyles!.classList).toBe(true);
      expect(shellStyles!.gridTemplateColumns).toContain('72px');
    });

    test('C03: 内容区 max-width = 1440px', async ({ authenticatedPage: page }) => {
      const pageStyles = await page.evaluate(() => {
        const pageEl = document.querySelector('.page');
        if (!pageEl) return null;
        const styles = getComputedStyle(pageEl);
        return {
          maxWidth: styles.maxWidth,
        };
      });

      expect(pageStyles).not.toBeNull();
      expect(pageStyles!.maxWidth).toBe('1440px');
    });

    test('C04: 内容区 padding = 22px 24px 44px', async ({ authenticatedPage: page }) => {
      const pageStyles = await page.evaluate(() => {
        const pageEl = document.querySelector('.page');
        if (!pageEl) return null;
        const styles = getComputedStyle(pageEl);
        return {
          paddingTop: styles.paddingTop,
          paddingRight: styles.paddingRight,
          paddingBottom: styles.paddingBottom,
          paddingLeft: styles.paddingLeft,
        };
      });

      expect(pageStyles).not.toBeNull();
      expect(pageStyles!.paddingTop).toBe('22px');
      expect(pageStyles!.paddingRight).toBe('24px');
      expect(pageStyles!.paddingBottom).toBe('44px');
      expect(pageStyles!.paddingLeft).toBe('24px');
    });
  });

  test.describe('侧边栏交互', () => {
    test.beforeEach(async ({ authenticatedPage: page }) => {
      // 确保侧边栏处于展开状态
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      // 清除 localStorage 中的折叠状态
      await page.evaluate(() => {
        localStorage.setItem('prototype-sidebar-collapsed', 'false');
      });
      await page.reload();
      await page.waitForLoadState('networkidle');
    });

    test('C05: 点击折叠按钮 → .shell 添加 collapsed 类', async ({ authenticatedPage: page }) => {
      const toggleBtn = page.locator('.toggle-btn');
      await expect(toggleBtn).toBeVisible();

      // 点击前确认未折叠
      const shellBefore = page.locator('.shell');
      await expect(shellBefore).not.toHaveClass(/collapsed/);

      await toggleBtn.click();
      await page.waitForTimeout(300);

      // 点击后确认已折叠
      const shellAfter = page.locator('.shell');
      await expect(shellAfter).toHaveClass(/collapsed/);
    });

    test('C06: 折叠后 localStorage prototype-sidebar-collapsed = true', async ({ authenticatedPage: page }) => {
      const toggleBtn = page.locator('.toggle-btn');
      await toggleBtn.click();
      await page.waitForTimeout(300);

      const stored = await page.evaluate(() => {
        return localStorage.getItem('prototype-sidebar-collapsed');
      });

      expect(stored).toBe('true');
    });

    test('C07: 刷新页面后折叠状态持久化', async ({ authenticatedPage: page }) => {
      // 先折叠
      const toggleBtn = page.locator('.toggle-btn');
      await toggleBtn.click();
      await page.waitForTimeout(300);

      // 刷新页面
      await page.reload();
      await page.waitForLoadState('networkidle');

      // 验证折叠状态保持
      const shell = page.locator('.shell');
      await expect(shell).toHaveClass(/collapsed/);
    });

    test('C08: 展开后 localStorage 值更新为 false', async ({ authenticatedPage: page }) => {
      // 先折叠
      const toggleBtn = page.locator('.toggle-btn');
      await expect(toggleBtn).toBeVisible({ timeout: 5000 });
      await toggleBtn.click();
      await page.waitForTimeout(500);

      // 再展开
      await toggleBtn.click();
      await page.waitForTimeout(500);

      const stored = await page.evaluate(() => {
        return localStorage.getItem('prototype-sidebar-collapsed');
      });

      expect(stored).toBe('false');

      // 验证 shell 没有 collapsed 类
      const shell = page.locator('.shell');
      await expect(shell).not.toHaveClass(/collapsed/);
    });

    test('C09: 导航菜单点击跳转正确', async ({ authenticatedPage: page }) => {
      // 测试多个导航目标
      const navTargets = [
        { path: '/customers', text: '客户管理', needExpand: false },
        { path: '/billing/balances', text: '余额管理', needExpand: true, parent: '结算管理' },
        { path: '/analytics/consumption', text: '消耗分析', needExpand: true, parent: '客户分析' },
      ];

      for (const target of navTargets) {
        // 如果需要展开子菜单，先点击父级菜单
        if (target.needExpand) {
          const parent = page.locator('.nav-parent').filter({ hasText: target.parent! });
          if (await parent.isVisible({ timeout: 3000 }).catch(() => false)) {
            await parent.click();
            await page.waitForTimeout(300);
          }
        }

        // 点击导航按钮
        const navBtn = page.locator('.nav-btn').filter({ hasText: target.text });
        await expect(navBtn.first()).toBeVisible({ timeout: 5000 });
        await navBtn.first().click();
        await page.waitForLoadState('domcontentloaded');

        // 验证 URL
        await expect(page).toHaveURL(new RegExp(target.path));
      }
    });

    test('C10: 子菜单展开/折叠', async ({ authenticatedPage: page }) => {
      // 点击“结算管理”父级菜单（使用 .nav-parent 选择器）
      const billingParent = page.locator('.nav-parent').filter({ hasText: '结算管理' });
      await expect(billingParent).toBeVisible();
      await billingParent.click();
      await page.waitForTimeout(300);

      // 验证子菜单项可见
      const balanceItem = page.locator('.nav-btn.sub').filter({ hasText: '余额管理' });
      await expect(balanceItem).toBeVisible({ timeout: 3000 });

      // 点击“客户分析”父级菜单
      const analyticsParent = page.locator('.nav-parent').filter({ hasText: '客户分析' });
      await expect(analyticsParent).toBeVisible();
      await analyticsParent.click();
      await page.waitForTimeout(300);

      // 验证子菜单项可见
      const consumptionItem = page.locator('.nav-btn.sub').filter({ hasText: '消耗分析' });
      await expect(consumptionItem).toBeVisible({ timeout: 3000 });
    });

    test('C11: active 菜单项 aria-current="page" 属性正确', async ({ authenticatedPage: page }) => {
      // 在首页时，运营工作台应有 aria-current="page"
      const homeNav = page.locator('.nav-btn').filter({ hasText: '运营工作台' });
      await expect(homeNav).toHaveAttribute('aria-current', 'page');

      // 导航到客户管理
      const customersNav = page.locator('.nav-btn').filter({ hasText: '客户管理' });
      await expect(customersNav).toBeVisible({ timeout: 5000 });
      await customersNav.click();
      await page.waitForLoadState('domcontentloaded');
      await expect(customersNav).toHaveAttribute('aria-current', 'page');

      // 首页导航不应再有 aria-current
      await expect(homeNav).not.toHaveAttribute('aria-current', 'page');
    });
  });

  test.describe('顶栏交互', () => {
    test.beforeEach(async ({ authenticatedPage: page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    });

    test('C12: 搜索框 role="search" + aria-label="全局搜索"', async ({ authenticatedPage: page }) => {
      const search = page.locator('.search');
      await expect(search).toBeVisible();
      await expect(search).toHaveAttribute('role', 'search');
      await expect(search).toHaveAttribute('aria-label', '全局搜索');
    });

    test('C13: 按 / 键聚焦搜索框', async ({ authenticatedPage: page }) => {
      // 确保当前焦点不在搜索框
      await page.locator('body').click();

      // 按 / 键
      await page.keyboard.press('/');

      // 验证搜索框获得焦点
      const searchInput = page.locator('.search input');
      await expect(searchInput).toBeFocused();
    });

    test('C14: 搜索框 Enter 触发搜索提示', async ({ authenticatedPage: page }) => {
      const searchInput = page.locator('.search input');

      // 填入搜索关键词
      await searchInput.fill('测试搜索');
      await searchInput.press('Enter');

      // 验证出现搜索提示消息（info 或 warning 类型）
      const message = page.locator('.arco-message-info, .arco-message-warning, .arco-message-success');
      await expect(message.first()).toBeVisible({ timeout: 5000 });
    });
  });
});
