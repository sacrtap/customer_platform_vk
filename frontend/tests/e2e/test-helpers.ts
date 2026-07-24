import { Page, expect } from '@playwright/test';
import * as http from 'http';

/**
 * 客户管理 E2E 测试公共工具
 *
 * 提供：
 * - API 数据准备（通过 Node.js HTTP 调用后端 API）
 * - UI 交互辅助函数（Arco Design 组件操作）
 * - 通用断言和选择器
 */

// ===================== 常量 =====================

export const TEST_CONFIG = {
  apiHost: 'localhost',
  apiPort: 8000,
  apiBase: '/api/v1',
  adminUsername: 'admin',
  adminPassword: 'admin123',
};

/** 生成唯一的测试公司 ID（避免冲突）— company_id 在数据库中为 INTEGER (int32) 类型，最大值 2147483647 */
export function generateTestCompanyId(_suffix: string = ''): number {
  // 使用时间戳后6位 + 随机4位，确保在 int32 范围内（最大 ~999999999）
  const timestamp = Date.now() % 1000000;
  const random = Math.floor(Math.random() * 9000) + 1000;
  return timestamp * 1000 + random;
}

/** 生成唯一的测试客户名称 */
export function generateTestCustomerName(suffix: string = ''): string {
  const timestamp = Date.now();
  return `测试客户_${timestamp}${suffix ? '_' + suffix : ''}`;
}

// ===================== Node.js HTTP 工具 =====================

/** 发起 HTTP 请求到后端 API */
function apiRequest(method: string, path: string, body?: Record<string, unknown>, headers?: Record<string, string>): Promise<{ status: number; data: Record<string, unknown> }> {
  return new Promise((resolve, reject) => {
    const options: http.RequestOptions = {
      hostname: TEST_CONFIG.apiHost,
      port: TEST_CONFIG.apiPort,
      path,
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode || 0, data: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode || 0, data: { raw: data } });
        }
      });
    });

    req.on('error', reject);
    req.setTimeout(15000, () => { req.destroy(); reject(new Error('Request timeout')); });

    if (body) {
      req.write(JSON.stringify(body));
    }
    req.end();
  });
}

// ===================== API 数据准备 =====================

/** 通过后端 API 登录并获取 JWT Token */
export async function apiLogin(): Promise<string> {
  const { data } = await apiRequest('POST', `${TEST_CONFIG.apiBase}/auth/login`, {
    username: TEST_CONFIG.adminUsername,
    password: TEST_CONFIG.adminPassword,
  });

  if (data.code !== 0) {
    throw new Error(`API 登录失败: ${data.message || JSON.stringify(data)}`);
  }

  return data.data?.access_token || data.data?.token;
}

/** 通过后端 API 创建测试客户 */
export async function apiCreateCustomer(token: string, data: {
  company_id: number;
  name: string;
  email?: string;
  account_type?: string;
  industry?: string;
  industry_type_id?: number;
  settlement_type?: string;
  settlement_cycle?: string;
  is_key_customer?: boolean;
  manager_id?: number;
}): Promise<Record<string, unknown>> {
  const { status, data: response } = await apiRequest(
    'POST', `${TEST_CONFIG.apiBase}/customers`, data,
    { 'Authorization': `Bearer ${token}` }
  );

  if (status !== 201 && status !== 200) {
    throw new Error(`API 创建客户失败: ${status} - ${JSON.stringify(response)}`);
  }

  return response;
}

/** 通过后端 API 删除客户（软删除） */
export async function apiDeleteCustomer(token: string, customerId: number): Promise<void> {
  await apiRequest('DELETE', `${TEST_CONFIG.apiBase}/customers/${customerId}`, undefined, {
    'Authorization': `Bearer ${token}`,
  });
}

/** 通过后端 API 获取客户列表 */
export async function apiGetCustomers(token: string, params: Record<string, string> = {}): Promise<Record<string, unknown>> {
  const query = new URLSearchParams(params).toString();
  const path = `${TEST_CONFIG.apiBase}/customers${query ? '?' + query : ''}`;

  const { data } = await apiRequest('GET', path, undefined, {
    'Authorization': `Bearer ${token}`,
  });

  return data;
}

/** 通过后端 API 给指定客户充值 */
export async function apiRecharge(token: string, customerId: number, realAmount: number = 1000, bonusAmount: number = 0): Promise<Record<string, unknown>> {
  const { status, data: response } = await apiRequest(
    'POST', `${TEST_CONFIG.apiBase}/billing/recharge`,
    {
      customer_id: customerId,
      real_amount: realAmount,
      bonus_amount: bonusAmount,
      remark: 'E2E 测试充值',
    },
    { 'Authorization': `Bearer ${token}` }
  );

  if (status !== 201 && status !== 200) {
    throw new Error(`API 充值失败: ${status} - ${JSON.stringify(response)}`);
  }

  return response;
}

/** 通过后端 API 更新客户字段 */
export async function apiUpdateCustomer(token: string, customerId: number, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { status, data: response } = await apiRequest(
    'PUT', `${TEST_CONFIG.apiBase}/customers/${customerId}`, data,
    { 'Authorization': `Bearer ${token}` }
  );

  if (status !== 200) {
    throw new Error(`API 更新客户失败: ${status} - ${JSON.stringify(response)}`);
  }

  return response;
}

// ===================== UI 交互辅助函数 =====================

/** 登录到应用（UI 方式） */
export async function uiLogin(page: Page): Promise<void> {
  await page.goto('/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 10000 });
  await page.fill('input[field="username"], input[type="text"]', TEST_CONFIG.adminUsername);
  await page.fill('input[field="password"], input[type="password"]', TEST_CONFIG.adminPassword);
  await page.click('button[type="submit"], button:has-text("登录")');
  await page.waitForURL(/\/$|\/customers/, { timeout: 30000, waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
}

/** 等待 Arco Design 消息提示出现并验证 */
export async function waitForMessage(page: Page, type: 'success' | 'error' | 'warning' | 'info', timeout: number = 10000): Promise<void> {
  const selector = `.arco-message-${type}`;
  await page.waitForSelector(selector, { timeout, state: 'visible' });
}

/** 获取当前可见的 Modal 定位器（使用 Playwright :visible 引擎，取最后一个打开的弹窗） */
export function getVisibleModal(page: Page) {
  return page.locator('.arco-modal:visible').last();
}

/** 等待 Arco Design Modal 对话框出现 */
export async function waitForModal(page: Page, timeout: number = 10000): Promise<void> {
  await page.locator('.arco-modal:visible').first().waitFor({ state: 'visible', timeout });
}

/** 关闭当前打开的 Modal */
export async function closeModal(page: Page): Promise<void> {
  const modal = page.locator('.arco-modal:visible').last();
  const cancelBtn = modal.locator('.arco-modal-footer button:has-text("取消")');
  if (await cancelBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await cancelBtn.click();
  } else {
    const closeBtn = modal.locator('.arco-modal-close-btn');
    if (await closeBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await closeBtn.click();
    } else {
      await page.keyboard.press('Escape');
    }
  }
  await page.locator('.arco-modal:visible').waitFor({ state: 'hidden', timeout: 5000 }).catch(() => {});
}

/** 在 Arco Design Select 中选择选项（通过文本） */
export async function selectOptionByText(page: Page, selectSelector: string, optionText: string): Promise<void> {
  const select = page.locator(selectSelector);
  await select.click();
  await page.waitForTimeout(300);

  const option = page.locator('.arco-select-option', { hasText: optionText });
  await option.waitFor({ state: 'visible', timeout: 5000 });
  await option.click();
  await page.waitForTimeout(300);
}

/** 填写 Arco Design 表单字段（自动限定在可见弹窗内） */
export async function fillFormField(page: Page, label: string, value: string): Promise<void> {
  // 优先在可见弹窗中查找表单项
  const modalFormItem = page.locator('.arco-modal:visible .arco-form-item', { has: page.locator(`text=${label}`) });
  const modalCount = await modalFormItem.count();

  let formItem;
  if (modalCount > 0) {
    formItem = modalFormItem.first();
  } else {
    // 回退到全页面查找
    formItem = page.locator('.arco-form-item', { has: page.locator(`text=${label}`) }).first();
  }

  const input = formItem.locator('input:not([type="hidden"])').first();

  if (await input.isVisible({ timeout: 2000 })) {
    await input.fill(value);
    return;
  }

  const textarea = formItem.locator('textarea').first();
  if (await textarea.isVisible({ timeout: 2000 })) {
    await textarea.fill(value);
    return;
  }

  throw new Error(`未找到表单项 "${label}" 的输入控件`);
}

/** 等待表格加载完成（支持 Arco 表格、自定义表格、空表状态） */
export async function waitForTableLoaded(page: Page, timeout: number = 15000): Promise<void> {
  // 等待加载动画消失（Arco 表格）
  await page.waitForSelector('.arco-table .arco-spin-loading', {
    state: 'hidden',
    timeout,
  }).catch(() => {});

  // 等待自定义表格的 loading 状态消失
  await page.waitForSelector('.loading-state', {
    state: 'hidden',
    timeout,
  }).catch(() => {});

  // 等待表格 body 存在（Arco 表格 或 自定义表格）
  await page.waitForSelector('.arco-table tbody, .table-section tbody, table.table tbody', { timeout }).catch(() => {});

  // 额外等待，确保数据渲染完成
  await page.waitForTimeout(500).catch(() => {});
}

/** 获取表格中的数据行数 */
export async function getTableRowCount(page: Page): Promise<number> {
  return page.locator('.arco-table tbody tr').count();
}

// ===================== 通用断言 =====================

/** 断言表格中至少有一行包含指定文本（支持 Arco 表格和自定义表格） */
export async function expectTableRowContains(page: Page, text: string, timeout: number = 15000): Promise<void> {
  await waitForTableLoaded(page);
  const matchingRows = page.locator('.arco-table tbody tr, .table-section tbody tr, table tbody tr', { hasText: text });
  await expect(matchingRows.first()).toBeVisible({ timeout });
}

/** 清除筛选器（行业、账号类型等默认筛选） */
export async function clearFilters(page: Page): Promise<void> {
  // 清除「账号类型」筛选（单选 FilterDropdown）
  const accountTypeTrigger = page.locator('.filter-dropdown', { hasText: '账号类型' }).locator('.filter-trigger');
  if (await accountTypeTrigger.isVisible({ timeout: 2000 }).catch(() => false)) {
    await accountTypeTrigger.click();
    await page.waitForTimeout(300);
    // 点击「全部」选项
    const allOption = page.locator('.filter-panel .filter-option', { hasText: '全部' }).first();
    if (await allOption.isVisible({ timeout: 2000 }).catch(() => false)) {
      await allOption.click();
      await page.waitForTimeout(300);
    }
  }

  // 清除「行业」筛选（多选 FilterDropdown）
  const industryTrigger = page.locator('.filter-dropdown', { hasText: '行业' }).locator('.filter-trigger');
  if (await industryTrigger.isVisible({ timeout: 2000 }).catch(() => false)) {
    await industryTrigger.click();
    await page.waitForTimeout(300);
    // 点击「全部」选项
    const allOption = page.locator('.filter-panel .filter-option', { hasText: '全部' }).first();
    if (await allOption.isVisible({ timeout: 2000 }).catch(() => false)) {
      await allOption.click();
      await page.waitForTimeout(300);
    }
    // 多选需要点击「确认」
    const confirmBtn = page.locator('.filter-panel .btn-confirm').first();
    if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await confirmBtn.click();
      await page.waitForTimeout(300);
    }
  }
}

/** 搜索客户（填入关键词并点击筛选按钮） */
export async function searchCustomer(page: Page, keyword: string): Promise<void> {
  // 使用更精确的选择器：客户列表筛选区域的搜索框（排除全局搜索框）
  const searchInput = page.locator('.filters-container input[placeholder*="搜索"], .filters input[placeholder*="搜索"]').first();

  // 清空输入框
  await searchInput.click();
  await searchInput.fill('');

  // 逐字符输入，确保 Vue v-model 正确响应
  await searchInput.pressSequentially(keyword, { delay: 30 });

  // 等待 debounce（300ms）和联想请求完成
  await page.waitForTimeout(1000);

  // 点击页面标题区域关闭联想下拉框（不使用 Escape，因为组件不监听 Escape）
  await page.locator('h1').first().click().catch(() => {});
  await page.waitForTimeout(500);

  // 点击筛选按钮（此时联想框已关闭，不需要 force）
  await page.locator('.filters button:has-text("筛选")').first().click();
  await waitForTableLoaded(page);
}

/** 断言 Arco Design 消息提示出现 */
export async function expectMessage(page: Page, type: 'success' | 'error' | 'warning' | 'info', text?: string): Promise<void> {
  const message = page.locator(`.arco-message-${type}`);
  await expect(message.first()).toBeVisible();
  if (text) {
    await expect(message.filter({ hasText: text }).first()).toBeVisible();
  }
}

/** 断言客户详情 Tab 存在并可点击 */
export async function expectTabExists(page: Page, tabName: string): Promise<void> {
  const tab = page.locator(`.arco-tabs-tab:has-text("${tabName}")`);
  await expect(tab.first()).toBeVisible();
}

/** 点击客户详情 Tab */
export async function clickTab(page: Page, tabName: string): Promise<void> {
  const tab = page.locator(`.arco-tabs-tab:has-text("${tabName}")`);
  await tab.first().click();
  await page.waitForTimeout(500);
}

// ===================== 确认对话框操作 =====================

/** 确认 Arco Design 确认对话框 */
export async function confirmDialog(page: Page): Promise<void> {
  const popconfirmOk = page.locator('.arco-popconfirm .arco-btn-primary');
  if (await popconfirmOk.isVisible({ timeout: 3000 }).catch(() => false)) {
    await popconfirmOk.click();
    return;
  }

  // 优先在可见的 Modal 中查找确认按钮
  const visibleModal = page.locator('.arco-modal:visible').last();
  const modalOk = visibleModal.locator('.arco-btn-primary, button:has-text("确定")');
  if (await modalOk.first().isVisible({ timeout: 3000 }).catch(() => false)) {
    await modalOk.first().click();
    return;
  }

  throw new Error('未找到确认对话框');
}
