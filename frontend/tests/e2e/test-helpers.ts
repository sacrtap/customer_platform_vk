import { Page, expect, APIRequestContext } from '@playwright/test';
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

/** 生成唯一的测试公司 ID（避免冲突） */
export function generateTestCompanyId(suffix: string = ''): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 6);
  return `TEST_${timestamp}_${random}${suffix ? '_' + suffix : ''}`;
}

/** 生成唯一的测试客户名称 */
export function generateTestCustomerName(suffix: string = ''): string {
  const timestamp = Date.now();
  return `测试客户_${timestamp}${suffix ? '_' + suffix : ''}`;
}

// ===================== Node.js HTTP 工具 =====================

/** 发起 HTTP 请求到后端 API */
function apiRequest(method: string, path: string, body?: any, headers?: Record<string, string>): Promise<{ status: number; data: any }> {
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
  company_id: string;
  name: string;
  email?: string;
  account_type?: string;
  industry?: string;
  customer_level?: string;
  settlement_type?: string;
  settlement_cycle?: string;
  is_key_customer?: boolean;
  manager_id?: number;
}): Promise<any> {
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
export async function apiGetCustomers(token: string, params: Record<string, string> = {}): Promise<any> {
  const query = new URLSearchParams(params).toString();
  const path = `${TEST_CONFIG.apiBase}/customers${query ? '?' + query : ''}`;
  
  const { data } = await apiRequest('GET', path, undefined, {
    'Authorization': `Bearer ${token}`,
  });

  return data;
}

/** 通过后端 API 给指定客户充值 */
export async function apiRecharge(token: string, customerId: number, realAmount: number = 1000, bonusAmount: number = 0): Promise<any> {
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
export async function apiUpdateCustomer(token: string, customerId: number, data: Record<string, any>): Promise<any> {
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

/** 等待 Arco Design Modal 对话框出现 */
export async function waitForModal(page: Page, timeout: number = 10000): Promise<void> {
  // Wait for the modal mask to be visible (indicates modal is showing)
  await page.waitForFunction(() => {
    const mask = document.querySelector('.arco-modal-mask');
    if (mask) return true;
    const wrappers = document.querySelectorAll('.arco-modal-wrapper');
    for (const w of wrappers) {
      if (w.clientHeight > 0 && w.querySelector('.arco-modal')) return true;
    }
    // Fallback: check for visible modal
    const modals = document.querySelectorAll('.arco-modal');
    for (const m of modals) {
      if (m.closest('[style*="display: none"]') === null && m.parentElement?.parentElement?.getAttribute('style')?.includes('display: none') !== true) {
        return true;
      }
    }
    return false;
  }, { timeout });
}

/** 关闭当前打开的 Modal */
export async function closeModal(page: Page): Promise<void> {
  const cancelBtn = page.locator('.arco-modal-footer button:has-text("取消")');
  if (await cancelBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await cancelBtn.click();
  } else {
    const closeBtn = page.locator('.arco-modal-close-btn');
    if (await closeBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await closeBtn.click();
    } else {
      await page.keyboard.press('Escape');
    }
  }
  await page.waitForSelector('.arco-modal', { state: 'hidden', timeout: 5000 }).catch(() => {});
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

/** 填写 Arco Design 表单字段 */
export async function fillFormField(page: Page, label: string, value: string): Promise<void> {
  const formItem = page.locator('.arco-form-item', { has: page.locator(`text=${label}`) });
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

/** 等待表格加载完成 */
export async function waitForTableLoaded(page: Page, timeout: number = 15000): Promise<void> {
  await page.waitForSelector('.arco-table .arco-spin-loading', {
    state: 'hidden',
    timeout,
  }).catch(() => {});
  
  await Promise.race([
    page.waitForSelector('.arco-table tbody tr', { timeout }),
    page.waitForSelector('.arco-empty', { timeout }),
  ]);
}

/** 获取表格中的数据行数 */
export async function getTableRowCount(page: Page): Promise<number> {
  return page.locator('.arco-table tbody tr').count();
}

// ===================== 通用断言 =====================

/** 断言表格中至少有一行包含指定文本 */
export async function expectTableRowContains(page: Page, text: string): Promise<void> {
  await waitForTableLoaded(page);
  const matchingRows = page.locator('.arco-table tbody tr', { hasText: text });
  await expect(matchingRows.first()).toBeVisible();
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
  
  const modalOk = page.locator('.arco-modal .arco-btn-primary, .arco-modal button:has-text("确定")');
  if (await modalOk.first().isVisible({ timeout: 3000 }).catch(() => false)) {
    await modalOk.first().click();
    return;
  }
  
  throw new Error('未找到确认对话框');
}
