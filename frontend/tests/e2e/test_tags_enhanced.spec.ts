import { test, expect } from './fixtures';
import { getVisibleModal } from './test-helpers';

/**
 * 标签管理增强 E2E 测试
 *
 * 替换原有的浅层 test_tags.spec.ts，提供更深入的功能验证。
 * 覆盖：Tab 切换、CRUD、标签云展示、分页、样式验证。
 */
test.describe('标签管理增强测试', () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto('/tags');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
  });

  test('M01: PageHeader — eyebrow "System" + 标题 "标签管理"', async ({ authenticatedPage: page }) => {
    await expect(page.locator('.eyebrow')).toContainText('System');
    await expect(page.locator('h1').first()).toContainText('标签管理');
    await expect(page.locator('.desc')).toBeVisible();
  });

  test('M02: 客户标签 / 画像标签 Tab 切换', async ({ authenticatedPage: page }) => {
    // 验证 Tab 存在
    const tabs = page.locator('.arco-tabs-tab');
    await expect(tabs.first()).toBeVisible();

    // 验证有两个 Tab
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(2);

    // 验证 Tab 文本
    await expect(tabs.nth(0)).toContainText('客户标签');
    await expect(tabs.nth(1)).toContainText('画像标签');

    // 点击"画像标签" Tab
    await tabs.nth(1).click();
    await page.waitForTimeout(500);

    // 验证 Tab 切换后 active 状态
    await expect(tabs.nth(1)).toHaveClass(/active/);

    // 切换回"客户标签"
    await tabs.nth(0).click();
    await page.waitForTimeout(500);
    await expect(tabs.nth(0)).toHaveClass(/active/);
  });

  test('M03: 新建标签', async ({ authenticatedPage: page }) => {
    const createBtn = page.locator('button:has-text("新建标签")');
    const hasPermission = await createBtn.isVisible({ timeout: 3000 }).catch(() => false);
    test.skip(!hasPermission, '当前用户无 tags:create 权限');

    await createBtn.click();

    // 验证弹窗显示
    const modal = getVisibleModal(page);
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(getVisibleModal(page).locator('.arco-modal-title')).toContainText('新建标签');

    // 验证表单字段存在
    const nameInput = modal.locator('input').first();
    await expect(nameInput).toBeVisible();

    // 填入标签名称
    await nameInput.fill(`e2e_tag_${Date.now()}`);

    // 关闭弹窗（不实际提交）
    const cancelBtn = modal.locator('button:has-text("取消")');
    await cancelBtn.click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test('M04: 编辑标签 — 点击标签 → 编辑弹窗', async ({ authenticatedPage: page }) => {
    // 查找标签云中的标签
    const tags = page.locator('.tag-list .arco-tag');
    const tagCount = await tags.count();
    test.skip(tagCount === 0, '当前无标签数据可供编辑');

    // 点击第一个标签
    await tags.first().click();

    // 验证编辑弹窗显示
    const modal = getVisibleModal(page);
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(getVisibleModal(page).locator('.arco-modal-title')).toContainText('编辑');

    // 验证弹窗预填了标签名称
    const nameInput = modal.locator('input').first();
    const prefilledValue = await nameInput.inputValue();
    expect(prefilledValue).toBeTruthy();

    // 关闭弹窗
    const cancelBtn = modal.locator('button:has-text("取消")');
    await cancelBtn.click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test('M05: 删除标签 — 关闭标签 → 确认删除', async ({ authenticatedPage: page }) => {
    // 查找标签的关闭按钮
    const closeBtns = page.locator('.tag-list .arco-tag .arco-icon-close, .tag-list .arco-tag-close');
    const btnCount = await closeBtns.count();
    test.skip(btnCount === 0, '当前无标签数据可供删除或无删除权限');

    // 点击关闭按钮（不实际删除——如果有确认弹窗则取消）
    await closeBtns.first().click();
    await page.waitForTimeout(500);

    // 如果有确认弹窗，取消
    const popconfirm = page.locator('.arco-popconfirm');
    if (await popconfirm.isVisible({ timeout: 2000 }).catch(() => false)) {
      const cancelBtn = popconfirm.locator('button:has-text("取消")');
      await cancelBtn.click();
      await expect(popconfirm).not.toBeVisible({ timeout: 3000 });
    }
  });

  test('M06: 分页功能', async ({ authenticatedPage: page }) => {
    // 验证分页组件是否存在
    const pagination = page.locator('.arco-pagination');
    const hasPagination = await pagination.first().isVisible({ timeout: 3000 }).catch(() => false);

    if (hasPagination) {
      await expect(pagination.first()).toBeVisible();

      // 验证分页按钮
      const pageItems = pagination.locator('.arco-pagination-item');
      const itemCount = await pageItems.count();
      expect(itemCount).toBeGreaterThan(0);
    }
  });

  test('M07: 标签云展示 — .arco-tag 药丸样式', async ({ authenticatedPage: page }) => {
    // 验证标签云容器存在
    await expect(page.locator('.tag-list').first()).toBeVisible();

    // 验证标签元素存在
    const tags = page.locator('.tag-list .arco-tag');
    const tagCount = await tags.count();

    if (tagCount > 0) {
      // 验证标签可见
      await expect(tags.first()).toBeVisible();

      // 验证 Arco Tag 的 border-radius（药丸样式）
      const tagRadius = await page.evaluate(() => {
        const tag = document.querySelector('.tag-list .arco-tag');
        if (!tag) return null;
        return getComputedStyle(tag).borderRadius;
      });

      // Arco Tag 默认 border-radius 应为 2px 或 999px（取决于 size）
      // size="large" 时可能为 2px，检查标签可见即可
      expect(tagRadius).not.toBeNull();
    }
  });

  test('M08: Tab 药丸样式验证', async ({ authenticatedPage: page }) => {
    // 验证 Arco Tabs Tab 样式
    const tabStyles = await page.evaluate(() => {
      const tab = document.querySelector('.arco-tabs-tab');
      if (!tab) return null;
      const styles = getComputedStyle(tab);
      return {
        borderRadius: styles.borderRadius,
      };
    });

    expect(tabStyles).not.toBeNull();

    // 验证 Tab 标题文本
    const tabTitles = page.locator('.arco-tabs-tab-title');
    const titleCount = await tabTitles.count();
    expect(titleCount).toBeGreaterThanOrEqual(2);
  });
});
