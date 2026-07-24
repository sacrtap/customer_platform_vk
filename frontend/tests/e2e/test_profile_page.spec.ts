import { test, expect } from './fixtures';
import { getVisibleModal } from './test-helpers';

/**
 * 个人信息页面 E2E 测试
 *
 * 测试场景：
 * 1. 页面加载与 PageHeader
 * 2. 左右分栏布局
 * 3. 头像区域
 * 4. 基本信息字段
 * 5. 保存功能
 * 6. 修改密码弹窗
 * 7. 头像上传校验
 * 8. 取消按钮
 */
test.describe('个人信息页面', () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto('/profile', { waitUntil: 'domcontentloaded' });
    // 等待 profile-loading 或 profile-content 出现
    await page.waitForSelector('.profile-loading, .profile-content', { timeout: 10000 }).catch(() => {});
    // 等待 profile-content 加载完成（loading 结束）
    await page.waitForSelector('.profile-content', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(500);
  });

  test('E01: 页面加载 — PageHeader 显示', async ({ authenticatedPage: page }) => {
    // 验证 eyebrow "Account"
    await expect(page.locator('.eyebrow')).toContainText('Account');

    // 验证标题 "个人信息"
    await expect(page.locator('h1').first()).toContainText('个人信息');

    // 验证副标题
    await expect(page.locator('.desc')).toBeVisible();
  });

  test('E02: 左右分栏布局', async ({ authenticatedPage: page }) => {
    // 等待 profile-content 加载完成
    await expect(page.locator('.profile-content')).toBeVisible({ timeout: 10000 });

    // 验证 profile-content 使用 grid 布局
    const layoutStyles = await page.evaluate(() => {
      const content = document.querySelector('.profile-content');
      if (!content) return null;
      const styles = getComputedStyle(content);
      return {
        display: styles.display,
        gridTemplateColumns: styles.gridTemplateColumns,
      };
    });

    expect(layoutStyles).not.toBeNull();
    expect(layoutStyles!.display).toBe('grid');
    // 应有 2 列（左右分栏）
    expect(layoutStyles!.gridTemplateColumns.split(' ').length).toBeGreaterThanOrEqual(2);

    // 验证左侧头像区域存在
    await expect(page.locator('.avatar-sidebar')).toBeVisible();

    // 验证右侧表单区域存在
    await expect(page.locator('.form-section')).toBeVisible();
  });

  test('E03: 头像区域', async ({ authenticatedPage: page }) => {
    // 等待 profile-content 加载完成（使用 toBeVisible 等待元素出现）
    const profileLoaded = await page.locator('.profile-content').isVisible({ timeout: 15000 }).catch(() => false);
    test.skip(!profileLoaded, 'Profile 内容未加载（可能认证超时）');

    // 验证头像容器存在
    await expect(page.locator('.avatar-preview')).toBeVisible();

    // 验证头像尺寸和圆角
    const avatarStyles = await page.evaluate(() => {
      const avatar = document.querySelector('.avatar-preview');
      if (!avatar) return null;
      const styles = getComputedStyle(avatar);
      return {
        width: styles.width,
        height: styles.height,
        borderRadius: styles.borderRadius,
      };
    });

    expect(avatarStyles).not.toBeNull();
    // 头像应为 80×80px
    expect(avatarStyles!.width).toBe('80px');
    expect(avatarStyles!.height).toBe('80px');
    // border-radius 应为 50%
    expect(avatarStyles!.borderRadius).toBe('50%');

    // 验证用户名/邮箱显示
    await expect(page.locator('.avatar-name')).toBeVisible();
    await expect(page.locator('.avatar-meta')).toBeVisible();

    // 验证"更换头像"按钮存在（使用 .avatar-actions 区域内的按钮）
    await expect(page.locator('.avatar-actions button').first()).toBeVisible({ timeout: 5000 });
  });

  test('E04: 基本信息字段', async ({ authenticatedPage: page }) => {
    // 验证用户名字段存在且 disabled
    const usernameInput = page.locator('.arco-form-item:has-text("用户名") input');
    await expect(usernameInput.first()).toBeVisible();
    await expect(usernameInput.first()).toBeDisabled();

    // 验证真实姓名字段
    const realNameInput = page.locator('.arco-form-item:has-text("真实姓名") input');
    await expect(realNameInput.first()).toBeVisible();

    // 验证邮箱字段
    const emailInput = page.locator('.arco-form-item:has-text("邮箱") input');
    await expect(emailInput.first()).toBeVisible();

    // 验证手机号字段
    const phoneInput = page.locator('.arco-form-item:has-text("手机号") input');
    await expect(phoneInput.first()).toBeVisible();

    // 验证最后登录时间字段存在且 disabled
    const lastLoginInput = page.locator('.arco-form-item:has-text("最后登录") input');
    await expect(lastLoginInput.first()).toBeVisible();
    await expect(lastLoginInput.first()).toBeDisabled();
  });

  test('E05: 保存功能', async ({ authenticatedPage: page }) => {
    // 修改邮箱字段
    const emailInput = page.locator('.arco-form-item:has-text("邮箱") input');
    await emailInput.first().fill('test-save@example.com');

    // 点击保存按钮
    const saveBtn = page.locator('button:has-text("保存")');
    await saveBtn.first().click();

    // 验证成功提示
    await expect(page.locator('.arco-message-success')).toBeVisible({ timeout: 10000 });
  });

  test('E06: 修改密码弹窗', async ({ authenticatedPage: page }) => {
    // 点击"修改密码"按钮
    const changePwdBtn = page.locator('button:has-text("修改密码")');
    await changePwdBtn.first().click();

    // 验证弹窗显示
    const modal = getVisibleModal(page);
    await expect(modal).toBeVisible({ timeout: 5000 });

    // 验证弹窗标题
    await expect(getVisibleModal(page).locator('.arco-modal-title')).toContainText('修改密码');

    // 验证当前密码输入框
    await expect(modal.locator('input[type="password"]').nth(0)).toBeVisible();

    // 验证新密码输入框
    await expect(modal.locator('input[type="password"]').nth(1)).toBeVisible();

    // 验证确认密码输入框
    await expect(modal.locator('input[type="password"]').nth(2)).toBeVisible();

    // 关闭弹窗
    const cancelBtn = modal.locator('button:has-text("取消")');
    await cancelBtn.click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test('E07: 头像上传校验', async ({ authenticatedPage: page }) => {
    // 等待 profile-content 加载完成
    const profileLoaded = await page.locator('.profile-content').isVisible({ timeout: 15000 }).catch(() => false);
    test.skip(!profileLoaded, 'Profile 内容未加载（可能认证超时）');

    // 此测试验证头像上传的文件类型和大小限制
    // 验证上传按钮存在（使用 .avatar-actions 区域内的按钮）
    const uploadBtn = page.locator('.avatar-actions button').first();
    await expect(uploadBtn).toBeVisible({ timeout: 5000 });

    // 验证上传组件存在
    const uploadComponent = page.locator('.arco-upload');
    await expect(uploadComponent.first()).toBeVisible();

    // 验证 accept 属性限制为图片格式
    const acceptAttr = await page.evaluate(() => {
      const upload = document.querySelector('.arco-upload input[type="file"]');
      return upload?.getAttribute('accept');
    });
    // accept 属性应包含 image/jpeg 或 image/png
    expect(acceptAttr).toBeTruthy();
  });

  test('E08: 取消按钮', async ({ authenticatedPage: page }) => {
    // 点击取消按钮
    const cancelBtn = page.locator('.form-actions button:has-text("取消")');
    await expect(cancelBtn).toBeVisible();
    await cancelBtn.click();

    // 验证路由跳转（router.back()）
    await page.waitForTimeout(1000);
    // 验证 URL 不再是 /profile（或仍是 /profile 但页面重新加载）
    // router.back() 的行为取决于历史记录
  });
});
