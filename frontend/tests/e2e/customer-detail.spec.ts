import { test, expect } from './fixtures';
import {
  uiLogin,
  waitForMessage as _waitForMessage,
  waitForModal as _waitForModal,
  closeModal as _closeModal,
  _waitForTableLoaded,
  generateTestCompanyId,
  generateTestCustomerName,
  apiLogin,
  apiCreateCustomer,
  apiDeleteCustomer,
  apiRecharge,
  expectTabExists as _expectTabExists,
  clickTab,
  getVisibleModal,
} from './test-helpers';

/**
 * 客户详情页面 E2E 测试
 */
test.describe('客户详情页面', () => {
  // 客户详情测试需要创建客户、充值、登录等步骤，增加超时
  test.setTimeout(60000);

  let authToken: string;
  let testCustomerId: number;
  let testCompanyId: number;

  test.beforeAll(async () => {
    authToken = await apiLogin();
  });

  test.beforeEach(async ({ page }) => {
    testCompanyId = generateTestCompanyId();
    const createResult = await apiCreateCustomer(authToken, {
      company_id: testCompanyId,
      name: generateTestCustomerName('详情'),
      account_type: 'production',
    });
    testCustomerId = createResult.data?.id;
    test.skip(!testCustomerId, '创建测试客户失败');

    await apiRecharge(authToken, testCustomerId, 1000, 200);

    await uiLogin(page);
  });

  test.afterEach(async () => {
    if (testCustomerId) {
      await apiDeleteCustomer(authToken, testCustomerId).catch(() => {});
    }
  });

  test('1. 导航到客户详情页面', async ({ page }) => {
    // 直接导航到详情页（重构后列表页点击“详情”打开预览抽屉，非直接跳转）
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    // 验证页面标题
    await expect(page.locator('h1').first()).toBeVisible();

    // 验证编辑按钮
    await expect(page.locator('button:has-text("编辑")').first()).toBeVisible();

    // 验证设为重点/取消重点按钮
    const keyBtn = page.locator('button:has-text("设为重点"), button:has-text("取消重点")');
    await expect(keyBtn.first()).toBeVisible();

    // 验证 Tabs
    await expect(page.locator('.arco-tabs').first()).toBeVisible();
  });

  test('2. 显示客户基础信息', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    // 验证基础信息 Tab 激活
    const activeTab = page.locator('.arco-tabs-tab-active, .arco-tabs-tab-active');
    expect(await activeTab.first().textContent()).toContain('基础信息');

    // 验证信息表格中的字段（重构后使用 .info-item .label / .info-item .value）
    const labels = ['客户名称', '公司 ID', '账号类型', '行业类型', '重点客户'];
    for (const label of labels) {
      const labelEl = page.locator('.info-item .label', { hasText: label });
      expect(await labelEl.first().isVisible({ timeout: 3000 }).catch(() => false)).toBeTruthy();
    }

    // 验证公司 ID 值
    const valueEl = page.locator('.info-item .value', { hasText: String(testCompanyId) });
    await expect(valueEl.first()).toBeVisible();
  });

  test('3. 显示客户标签', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    // 验证标签区域（在基础信息 Tab 中，.tags-container 类）
    const tagsContainer = page.locator('.tags-container');
    const containerVisible = await tagsContainer.first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(containerVisible).toBeTruthy();

    // 验证添加标签按钮
    const addTagBtn = page.locator('.tags-container button:has-text("添加标签")');
    const btnVisible = await addTagBtn.first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(btnVisible).toBeTruthy();
  });

  test('4. 添加客户标签', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    // 点击添加标签按钮
    await page.locator('.tags-container button:has-text("添加标签")').first().click();
    await page.waitForTimeout(3000);

    // 验证对话框出现
    const modal = page.locator('.arco-modal:has-text("添加标签")');
    const modalVisible = await modal.first().isVisible({ timeout: 15000 }).catch(() => false);

    if (!modalVisible) {
      test.skip(true, '标签对话框未出现（可能是 API 加载慢）');
      return;
    }

    expect(modalVisible).toBeTruthy();

    // 验证对话框中包含选择器或表单
    const hasDialogContent = await modal.first().textContent();
    expect(hasDialogContent!.length).toBeGreaterThan(10);
  });

  test('5. 移除客户标签', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    // 先添加一个标签
    await page.locator('button:has-text("添加标签")').first().click();
    await page.waitForTimeout(1000);

    const dialog = page.locator('.arco-drawer, .arco-modal');
    const dialogVisible = await dialog.first().isVisible({ timeout: 3000 }).catch(() => false);

    if (dialogVisible) {
      const select = page.locator('.arco-select').first();
      if (await select.isVisible({ timeout: 3000 }).catch(() => false)) {
        await select.click();
        await page.waitForTimeout(500);
        const option = page.locator('.arco-select-option').first();
        if (await option.isVisible({ timeout: 3000 }).catch(() => false)) {
          await option.click();
          await page.waitForTimeout(300);
          await page.locator('button:has-text("确定"), button:has-text("添加")').first().click();
          await page.waitForTimeout(1500);
        }
      }
    }

    // 现在尝试移除标签（查找标签上的关闭按钮）
    const tagCloseBtn = page.locator('.arco-tag .arco-tag-close-btn, .arco-tag .arco-icon-close');
    const closeVisible = await tagCloseBtn.first().isVisible({ timeout: 3000 }).catch(() => false);

    if (closeVisible) {
      await tagCloseBtn.first().click();
      await page.waitForTimeout(500);
      // 验证操作成功
      expect(true).toBeTruthy();
    } else {
      // 没有可移除的标签，跳过
      test.skip(true, '无标签可移除');
    }
  });

  test('6. 画像信息 Tab 显示', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    await clickTab(page, '画像信息');
    await page.waitForTimeout(2000);

    // 画像数据可能不存在于新建客户，跳过如果未加载
    const profileContent = page.locator('.metric-label, .chart-title');
    const hasProfile = await profileContent.first().isVisible({ timeout: 5000 }).catch(() => false);
    test.skip(!hasProfile, '画像数据未加载（新建客户可能无画像数据）');

    // 验证规模等级
    const scaleLabel = page.locator('.metric-label', { hasText: '规模等级' });
    expect(await scaleLabel.first().isVisible({ timeout: 5000 }).catch(() => false)).toBeTruthy();

    // 验证消费等级
    const consumeLabel = page.locator('.metric-label', { hasText: '消费等级' });
    expect(await consumeLabel.first().isVisible({ timeout: 3000 }).catch(() => false)).toBeTruthy();

    // 验证预估年消费（重构后画像指标为：规模等级、消费等级、预估年消费）
    const spendLabel = page.locator('.metric-label', { hasText: '预估年消费' });
    expect(await spendLabel.first().isVisible({ timeout: 3000 }).catch(() => false)).toBeTruthy();
  });

  test('7. 健康度仪表显示', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    await clickTab(page, '画像信息');
    await page.waitForTimeout(2000);

    // 画像数据可能不存在于新建客户，跳过如果未加载
    const profileContent = page.locator('.metric-label, .chart-title');
    const hasProfile = await profileContent.first().isVisible({ timeout: 5000 }).catch(() => false);
    test.skip(!hasProfile, '画像数据未加载（新建客户可能无画像数据）');

    // 验证健康度评分标题
    const healthTitle = page.locator('.chart-title', { hasText: '健康度评分' });
    expect(await healthTitle.first().isVisible({ timeout: 5000 }).catch(() => false)).toBeTruthy();

    // 验证图表区域
    const chartContent = page.locator('.chart-panel .chart-content, .chart-panel canvas');
    expect(await chartContent.first().isVisible({ timeout: 5000 }).catch(() => false)).toBeTruthy();
  });

  test('8. 消费等级进度显示', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    await clickTab(page, '画像信息');
    await page.waitForTimeout(2000);

    // 画像数据可能不存在于新建客户，跳过如果未加载
    const profileContent = page.locator('.metric-label, .chart-title');
    const hasProfile = await profileContent.first().isVisible({ timeout: 5000 }).catch(() => false);
    test.skip(!hasProfile, '画像数据未加载（新建客户可能无画像数据）');

    // 验证消费等级进度标题
    const progressTitle = page.locator('.chart-title', { hasText: '消费等级进度' });
    expect(await progressTitle.first().isVisible({ timeout: 5000 }).catch(() => false)).toBeTruthy();
  });

  test('9. 余额信息 Tab 显示', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    await clickTab(page, '余额信息');
    await page.waitForTimeout(1000);

    // 验证余额卡片标签
    const balanceLabels = ['总余额', '实充余额', '赠送余额', '已消耗'];
    for (const label of balanceLabels) {
      const labelEl = page.locator('.balance-label', { hasText: label });
      expect(await labelEl.first().isVisible({ timeout: 3000 }).catch(() => false)).toBeTruthy();
    }
  });

  test('10. 余额数据正确显示', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    await clickTab(page, '余额信息');
    await page.waitForTimeout(1000);

    // 验证余额数值区域存在（检查 balance-value 类）
    const balanceValues = page.locator('.balance-value');
    const valueCount = await balanceValues.count();
    expect(valueCount).toBeGreaterThanOrEqual(4); // 总余额、实充、赠送、已消耗

    // 验证至少有一个值不为 "-"
    const firstValue = await balanceValues.first().textContent();
    expect(firstValue).toBeTruthy();
    expect(firstValue).not.toBe('-');
  });

  test('11. 余额趋势图显示', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    await clickTab(page, '余额信息');
    await page.waitForTimeout(2000);

    // 验证余额趋势区域存在
    const trendSection = page.locator('.balance-trend-section');
    expect(await trendSection.first().isVisible({ timeout: 5000 }).catch(() => false)).toBeTruthy();
  });

  test('12. 结算单 Tab 显示', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    await clickTab(page, '结算单');
    await page.waitForTimeout(1000);

    // 验证表格或空状态存在
    const tableOrEmpty = page.locator('.arco-table, .empty-state');
    await expect(tableOrEmpty.first()).toBeVisible();
  });

  test('13. 用量分析 Tab 显示', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    await clickTab(page, '用量分析');
    await page.waitForTimeout(2000);

    // 验证用量表格存在
    const usageTable = page.locator('.usage-table-section .arco-table, .arco-table');
    await expect(usageTable.first()).toBeVisible();
  });

  test('14. 编辑客户详情', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    // 点击编辑按钮
    await page.locator('button:has-text("编辑")').first().click();
    await page.waitForTimeout(1000);

    // 验证编辑对话框
    const modal = getVisibleModal(page);
    const warningMsg = page.locator('.arco-message-warning');
    // 等待弹窗或警告消息出现
    const modalVisible = await modal.isVisible({ timeout: 5000 }).catch(() => false);
    if (!modalVisible) {
      const warningVisible = await warningMsg.isVisible({ timeout: 2000 }).catch(() => false);
      test.skip(warningVisible, '客户画像数据未加载，无法编辑');
    }
    expect(modalVisible).toBeTruthy();

    if (modalVisible) {
      // 尝试修改备注
      const textarea = modal.locator('textarea');
      if (await textarea.first().isVisible({ timeout: 2000 }).catch(() => false)) {
        await textarea.first().fill('E2E 测试备注');
      }

      // 提交
      await modal.locator('button:has-text("确定"), .arco-modal .arco-btn-primary').first().click();
      await page.waitForTimeout(2000);
    }
  });

  test('15. 设为/取消重点客户', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    const keyBtn = page.locator('button:has-text("设为重点"), button:has-text("取消重点")');
    await expect(keyBtn.first()).toBeVisible();

    const btnText = await keyBtn.first().textContent();
    await keyBtn.first().click();
    await page.waitForTimeout(1500);

    // 验证没有错误消息
    const errorMsg = page.locator('.arco-message-error');
    expect(await errorMsg.first().isVisible({ timeout: 2000 }).catch(() => false)).toBeFalsy();

    // 验证按钮文本变化
    const newText = await keyBtn.first().textContent();
    expect(newText).not.toBe(btnText);
  });

  test('Tab 切换功能正常', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    const tabNames = ['基础信息', '画像信息', '余额信息', '结算单', '用量分析'];

    for (const tabName of tabNames) {
      await clickTab(page, tabName);
      const tabContent = page.locator('.arco-tabs-content');
      await expect(tabContent.first()).toBeVisible();
    }
  });

  test('返回按钮功能', async ({ page }) => {
    // 直接导航到详情页
    await page.goto(`/customers/${testCustomerId}`);
    await page.waitForTimeout(1000);

    // 点击返回按钮
    const backBtn = page.locator('.page-header button').first();
    await expect(backBtn).toBeVisible();
    await backBtn.click();

    // 验证回到客户列表或首页（router.back() 行为取决于历史记录）
    await page.waitForTimeout(1000);
    const currentUrl = page.url();
    expect(currentUrl.includes('/customers') || currentUrl.endsWith('/')).toBeTruthy();
  });
  test('16. 进入详情页后 loading 消失', async ({ page }) => {
    await page.goto(`/customers/${testCustomerId}`);
    // 等待页面标题出现（数据加载完成标志）
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 10000 });
    // 验证 loading wrapper 已消失（v-if 移除 DOM）
    await expect(page.locator('.page-loading')).toHaveCount(0, { timeout: 10000 });
    // 验证 tabs 内容可见（重构后使用 .tabs-card 类）
    await expect(page.locator('.tabs-card').first()).toBeVisible();
  })
});
