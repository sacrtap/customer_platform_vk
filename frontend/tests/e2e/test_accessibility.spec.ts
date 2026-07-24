import { test, expect } from './fixtures';

/**
 * 无障碍测试
 *
 * 验证 aria 属性、键盘导航、焦点可见性和色彩对比度。
 * 确保重构后的页面符合 WCAG 无障碍标准。
 */
test.describe('无障碍测试', () => {
  test.describe('侧边栏无障碍', () => {
    test.beforeEach(async ({ authenticatedPage: page }) => {
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1000);
    });

    test('K01: 折叠按钮 aria-label 动态更新', async ({ authenticatedPage: page }) => {
      const toggleBtn = page.locator('.toggle-btn');
      await expect(toggleBtn).toBeVisible();

      // 展开态：aria-label = "收起侧边栏", aria-expanded = "true"
      await expect(toggleBtn).toHaveAttribute('aria-expanded', 'true');
      await expect(toggleBtn).toHaveAttribute('aria-label', '收起侧边栏');

      // 折叠
      await toggleBtn.click();
      await page.waitForTimeout(500);

      // 折叠态：aria-label = "展开侧边栏", aria-expanded = "false"
      await expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
      await expect(toggleBtn).toHaveAttribute('aria-label', '展开侧边栏');

      // 恢复展开
      await toggleBtn.click();
      await page.waitForTimeout(500);
    });

    test('K02: 导航 nav aria-label="主导航"', async ({ authenticatedPage: page }) => {
      const nav = page.locator('nav[aria-label="主导航"]');
      await expect(nav).toBeVisible();
    });

    test('K03: active 菜单项 aria-current="page"', async ({ authenticatedPage: page }) => {
      // 在首页时，运营工作台应有 aria-current="page"
      const homeNav = page.locator('.nav-btn').filter({ hasText: '运营工作台' });
      await expect(homeNav).toHaveAttribute('aria-current', 'page');
    });
  });

  test.describe('顶栏无障碍', () => {
    test('K04: 搜索框 role="search" + aria-label="全局搜索"', async ({ authenticatedPage: page }) => {
      const search = page.locator('.search');
      await expect(search).toBeVisible();
      await expect(search).toHaveAttribute('role', 'search');
      await expect(search).toHaveAttribute('aria-label', '全局搜索');
    });

    test('K05: SVG 图标 aria-hidden="true"', async ({ authenticatedPage: page }) => {
      // 检查顶栏中的装饰性 SVG 有 aria-hidden
      const svgs = page.locator('.top svg[aria-hidden="true"]');
      const count = await svgs.count();
      expect(count).toBeGreaterThan(0);
    });
  });

  test.describe('键盘导航', () => {
    test('K06: Tab 键可以在侧边栏菜单项之间循环', async ({ authenticatedPage: page }) => {
      // 点击页面空白处确保焦点不在输入框
      await page.locator('body').click();

      // 按 Tab 键多次，验证焦点在可交互元素之间移动
      const focusedElements: string[] = [];

      for (let i = 0; i < 5; i++) {
        await page.keyboard.press('Tab');
        await page.waitForTimeout(100);

        const focusedTag = await page.evaluate(() => {
          const el = document.activeElement;
          if (!el) return null;
          return {
            tag: el.tagName,
            class: el.className,
            text: el.textContent?.trim().substring(0, 20),
          };
        });

        if (focusedTag) {
          focusedElements.push(`${focusedTag.tag}.${focusedTag.class}`);
        }
      }

      // 验证至少有 2 个不同的元素获得焦点
      const uniqueFocused = new Set(focusedElements);
      expect(uniqueFocused.size).toBeGreaterThanOrEqual(2);
    });

    test('K07: / 键聚焦搜索框', async ({ authenticatedPage: page }) => {
      // 确保当前焦点不在输入框
      await page.locator('body').click();

      // 按 / 键
      await page.keyboard.press('/');

      // 验证搜索框获得焦点
      const searchInput = page.locator('.search input');
      await expect(searchInput).toBeFocused();
    });

    test('K08: Enter 键在搜索框中触发搜索', async ({ authenticatedPage: page }) => {
      const searchInput = page.locator('.search input');

      // 聚焦搜索框并输入
      await searchInput.click();
      await searchInput.fill('测试');
      await page.keyboard.press('Enter');

      // 验证出现搜索提示消息
      const message = page.locator('.arco-message-info, .arco-message-warning, .arco-message-success');
      await expect(message.first()).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('焦点可见性', () => {
    test.beforeEach(async ({ authenticatedPage: page }) => {
      const currentUrl = page.url();
      if (!currentUrl.endsWith('/') && !currentUrl.endsWith('#/')) {
        await page.goto('/');
        await page.waitForLoadState('domcontentloaded');
      }
      await page.waitForTimeout(500);
    });

    test('K09: 可交互元素 focus-visible 有 outline', async ({ authenticatedPage: page }) => {
      // 验证 :focus-visible 样式存在
      const focusStyleExists = await page.evaluate(() => {
        // 检查是否有 focus-visible 相关的 CSS 规则
        const styleSheets = document.styleSheets;
        for (const sheet of styleSheets) {
          try {
            const rules = sheet.cssRules;
            for (const rule of rules) {
              if (rule.cssText && rule.cssText.includes('focus-visible')) {
                return true;
              }
            }
          } catch {
            // 跨域样式表可能无法访问
          }
        }
        return false;
      });

      // 页面应包含 focus-visible 相关样式
      expect(focusStyleExists).toBe(true);

      // 验证按钮可以通过 Tab 聚焦
      await page.locator('body').click();
      await page.keyboard.press('Tab');
      await page.waitForTimeout(200);

      // 验证有元素获得焦点
      const hasFocus = await page.evaluate(() => {
        const el = document.activeElement;
        return el !== null && el !== document.body;
      });
      expect(hasFocus).toBe(true);
    });

    test('K10: 色彩对比度 — 正文文字与背景对比度 ≥ 4.5:1', async ({ authenticatedPage: page }) => {
      // 验证正文文字颜色与背景的对比度
      const contrastInfo = await page.evaluate(() => {
        // 获取 --ink 和 --bg 的值
        const rootStyles = getComputedStyle(document.documentElement);
        const inkColor = rootStyles.getPropertyValue('--ink').trim();
        const bgColorVar = rootStyles.getPropertyValue('--bg').trim();

        // 简单的对比度计算函数
        function hexToRgb(hex: string): [number, number, number] | null {
          const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
          return result ? [
            parseInt(result[1], 16),
            parseInt(result[2], 16),
            parseInt(result[3], 16),
          ] : null;
        }

        function getLuminance(rgb: [number, number, number]): number {
          const [r, g, b] = rgb.map(v => {
            const s = v / 255;
            return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
          });
          return 0.2126 * r + 0.7152 * g + 0.0722 * b;
        }

        function getContrastRatio(color1: string, color2: string): number | null {
          const rgb1 = hexToRgb(color1);
          const rgb2 = hexToRgb(color2);
          if (!rgb1 || !rgb2) return null;

          const l1 = getLuminance(rgb1);
          const l2 = getLuminance(rgb2);
          const lighter = Math.max(l1, l2);
          const darker = Math.min(l1, l2);
          return (lighter + 0.05) / (darker + 0.05);
        }

        const ratio = getContrastRatio(inkColor, bgColorVar);
        return { ratio, inkColor, bgColorVar };
      });

      // --ink (#0F172A) 与 --bg (#F6F8FB) 的对比度应 ≥ 4.5:1
      expect(contrastInfo.ratio).not.toBeNull();
      expect(contrastInfo.ratio).toBeGreaterThanOrEqual(4.5);
    });
  });
});
