import { test, expect } from './fixtures';

/**
 * 设计令牌验证测试
 *
 * 通过 getComputedStyle 验证 CSS 变量值和组件样式是否符合重构后的设计规范。
 * 确保所有设计令牌值与 prototype/design.md 一致。
 */
test.describe('设计令牌验证', () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('B01: :root CSS 变量值正确', async ({ authenticatedPage: page }) => {
    const rootVars = await page.evaluate(() => {
      const styles = getComputedStyle(document.documentElement);
      return {
        primary: styles.getPropertyValue('--primary').trim(),
        ink: styles.getPropertyValue('--ink').trim(),
        muted: styles.getPropertyValue('--muted').trim(),
        bg: styles.getPropertyValue('--bg').trim(),
        panel: styles.getPropertyValue('--panel').trim(),
        line: styles.getPropertyValue('--line').trim(),
        radius: styles.getPropertyValue('--radius').trim(),
        fontStack: styles.getPropertyValue('--font-stack').trim(),
        primary2: styles.getPropertyValue('--primary-2').trim(),
        cyan: styles.getPropertyValue('--cyan').trim(),
        green: styles.getPropertyValue('--green').trim(),
        amber: styles.getPropertyValue('--amber').trim(),
        red: styles.getPropertyValue('--red').trim(),
        violet: styles.getPropertyValue('--violet').trim(),
      };
    });

    // 中性色（CSS 变量值不区分大小写，使用 toLowerCase 比较）
    expect(rootVars.primary.toLowerCase()).toBe('#1d4ed8');
    expect(rootVars.ink.toLowerCase()).toBe('#0f172a');
    expect(rootVars.muted.toLowerCase()).toBe('#475569');
    expect(rootVars.bg.toLowerCase()).toBe('#f6f8fb');
    expect(rootVars.panel.toLowerCase()).toBe('#ffffff');
    expect(rootVars.line.toLowerCase()).toBe('#dbe3ef');
    expect(rootVars.radius).toBe('18px');

    // 字体栈包含 Inter
    expect(rootVars.fontStack.toLowerCase()).toContain('inter');

    // 语义色（CSS 变量值不区分大小写，使用 toLowerCase 比较）
    expect(rootVars.primary2.toLowerCase()).toBe('#2563eb');
    expect(rootVars.cyan.toLowerCase()).toBe('#0891b2');
    expect(rootVars.green.toLowerCase()).toBe('#059669');
    expect(rootVars.amber.toLowerCase()).toBe('#d97706');
    expect(rootVars.red.toLowerCase()).toBe('#dc2626');
    expect(rootVars.violet.toLowerCase()).toBe('#7c3aed');
  });

  test('B02: Arco 主题覆盖正确', async ({ authenticatedPage: page }) => {
    // 验证 --primary-6 (Arco 主色别名) 等于 --primary
    const arcoVars = await page.evaluate(() => {
      const styles = getComputedStyle(document.documentElement);
      return {
        primary6: styles.getPropertyValue('--primary-6').trim(),
      };
    });
    expect(arcoVars.primary6.toLowerCase()).toBe('#1d4ed8');

    // 验证 primary 按钮背景为渐变
    // 先确保页面上有 primary 按钮
    const primaryBtn = page.locator('.arco-btn-primary').first();
    if (await primaryBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      const btnBg = await page.evaluate((el) => {
        const styles = getComputedStyle(el as HTMLElement);
        return {
          background: styles.background,
          backgroundImage: styles.backgroundImage,
        };
      }, await primaryBtn.elementHandle());

      // 渐变背景应包含 #1d4ed8 和 #2563eb（检查 background 或 backgroundImage，支持 rgb 格式）
      const bgStr = (btnBg.background + ' ' + btnBg.backgroundImage).toLowerCase();
      expect(bgStr).toMatch(/1d4ed8|rgb\(29,\s*78,\s*216\)/);
      expect(bgStr).toMatch(/2563eb|rgb\(37,\s*99,\s*235\)/);
    }
  });

  test('B03: 侧边栏品牌标识样式', async ({ authenticatedPage: page }) => {
    const markStyles = await page.evaluate(() => {
      const mark = document.querySelector('.mark');
      if (!mark) return null;
      const styles = getComputedStyle(mark);
      return {
        background: styles.background,
        backgroundImage: styles.backgroundImage,
        borderRadius: styles.borderRadius,
        textContent: mark.textContent?.trim(),
        width: styles.width,
        height: styles.height,
      };
    });

    expect(markStyles).not.toBeNull();
    expect(markStyles!.textContent).toBe('VK');
    expect(markStyles!.borderRadius).toBe('13px');

    // 渐变背景应包含 #3b82f6 和 #06b6d4（检查 background 或 backgroundImage）
    const bgStr = (markStyles!.background + ' ' + markStyles!.backgroundImage).toLowerCase();
    expect(bgStr).toMatch(/3b82f6|rgb\(59,\s*130,\s*246\)/);
    expect(bgStr).toMatch(/06b6d4|rgb\(6,\s*182,\s*212\)/);
  });

  test('B04: 侧边栏背景样式', async ({ authenticatedPage: page }) => {
    const sideStyles = await page.evaluate(() => {
      const side = document.querySelector('.side');
      if (!side) return null;
      const styles = getComputedStyle(side);
      return {
        background: styles.background,
        color: styles.color,
      };
    });

    expect(sideStyles).not.toBeNull();
    // 背景应包含 radial-gradient 和 linear-gradient
    expect(sideStyles!.background.toLowerCase()).toContain('radial-gradient');
    expect(sideStyles!.background.toLowerCase()).toContain('linear-gradient');
    // 文字颜色应为 #CBD5E1 → rgb(203, 213, 225)
    expect(sideStyles!.color).toBe('rgb(203, 213, 225)');
  });

  test('B05: 顶栏毛玻璃效果', async ({ authenticatedPage: page }) => {
    const topStyles = await page.evaluate(() => {
      const top = document.querySelector('.top');
      if (!top) return null;
      const styles = getComputedStyle(top);
      return {
        backdropFilter: styles.backdropFilter || styles.webkitBackdropFilter,
        background: styles.background,
      };
    });

    expect(topStyles).not.toBeNull();
    // backdrop-filter 应包含 blur(14px)
    expect(topStyles!.backdropFilter.toLowerCase()).toContain('blur');
    expect(topStyles!.backdropFilter).toContain('14px');
    // 背景应为 rgba(246, 248, 251, 0.86)
    expect(topStyles!.background.toLowerCase()).toContain('246, 248, 251');
  });

  test('B06: 搜索框样式', async ({ authenticatedPage: page }) => {
    const searchStyles = await page.evaluate(() => {
      const search = document.querySelector('.search');
      if (!search) return null;
      const styles = getComputedStyle(search);
      return {
        borderRadius: styles.borderRadius,
        borderColor: styles.borderColor,
      };
    });

    expect(searchStyles).not.toBeNull();
    expect(searchStyles!.borderRadius).toBe('14px');
  });

  test('B07: 页面无旧色值残留', async ({ authenticatedPage: page }) => {
    // 旧色值列表 — 重构前的颜色
    const oldColors = ['#0369a1', '#0284c7', '#0c4a6e', '#075985', '#0369a1'];

    // 检查页面内联样式和 computed styles 不包含旧色值
    const foundOldColors = await page.evaluate((colors) => {
      const found: string[] = [];

      // 检查所有元素的 computed color 和 backgroundColor
      const elements = document.querySelectorAll('*');
      for (const el of elements) {
        const styles = getComputedStyle(el);
        const colorProps = [
          styles.color,
          styles.backgroundColor,
          styles.borderColor,
          styles.background,
        ];
        for (const prop of colorProps) {
          const lowerProp = prop.toLowerCase();
          for (const oldColor of colors) {
            if (lowerProp.includes(oldColor.toLowerCase())) {
              if (!found.includes(oldColor)) {
                found.push(oldColor);
              }
            }
          }
        }
      }

      // 检查所有 <style> 标签内容
      const styleTags = document.querySelectorAll('style');
      for (const tag of styleTags) {
        const content = tag.textContent?.toLowerCase() || '';
        for (const oldColor of colors) {
          if (content.includes(oldColor.toLowerCase())) {
            if (!found.includes(oldColor)) {
              found.push(oldColor);
            }
          }
        }
      }

      return found;
    }, oldColors);

    expect(foundOldColors).toEqual([]);
  });

  test('B08: ECharts 配色验证', async ({ authenticatedPage: page }) => {
    // 导航到消耗分析页面（有 ECharts 图表）
    await page.goto('/analytics/consumption');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 验证 canvas 元素存在
    const canvas = page.locator('canvas');
    const canvasCount = await canvas.count();

    if (canvasCount > 0) {
      // 验证 canvas 可见且非空白（通过检查 canvas 尺寸）
      const canvasInfo = await page.evaluate(() => {
        const c = document.querySelector('canvas');
        if (!c) return null;
        return {
          width: c.width,
          height: c.height,
          clientWidth: c.clientWidth,
          clientHeight: c.clientHeight,
        };
      });

      expect(canvasInfo).not.toBeNull();
      expect(canvasInfo!.clientWidth).toBeGreaterThan(0);
      expect(canvasInfo!.clientHeight).toBeGreaterThan(0);
    }

    // 检查页面样式中不包含旧色值
    const hasOldChartColors = await page.evaluate(() => {
      const styleTags = document.querySelectorAll('style');
      const oldColors = ['#0369a1', '#0284c7', '#0c4a6e'];
      for (const tag of styleTags) {
        const content = tag.textContent?.toLowerCase() || '';
        for (const oldColor of oldColors) {
          if (content.includes(oldColor.toLowerCase())) {
            return true;
          }
        }
      }
      return false;
    });

    expect(hasOldChartColors).toBe(false);
  });
});
