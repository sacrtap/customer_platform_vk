import { chromium, type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'node:url';

/**
 * Playwright 全局初始化：登录一次并保存 storageState
 *
 * 目的：
 *   E2E 套件中绝大多数用例（27/34 个文件使用 beforeEach）都需要「已登录」状态，
 *   而每个用例单独执行 UI 登录约需 2-3 秒（导航 + 填表 + 跳转 + 固定 1s 等待）。
 *   改为全局登录一次、由 storageState 注入后，单用例的登录开销降为「直接 goto」。
 *
 * 说明：
 * - 登录态存于 localStorage（见 src/stores/user.ts 的 access_token / user_info /
 *   user_permissions），storageState 可完整保存并复用；
 * - 依赖「未登录」的测试（如 test_login_flow.spec.ts 的登录/重定向用例）需用
 *   `test.use({ storageState: { cookies: [], origins: [] } })` 显式覆盖为空状态；
 * - 若 storageState 失效，test-helpers.uiLogin() 会自动回退到完整登录流程。
 *
 * 注意：frontend/package.json 为 `"type": "module"`，故用 fileURLToPath 取目录
 * （ESM 下没有 __dirname）。
 */
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_FILE = path.join(__dirname, '.auth', 'admin.json');

export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0]?.use?.baseURL ?? 'http://localhost:5173';

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(`${baseURL}/login`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 15000 });
  await page.fill('input[field="username"], input[type="text"]', 'admin');
  await page.fill('input[field="password"], input[type="password"]', 'admin123');
  await page.click('button[type="submit"], button:has-text("登录")');
  await page.waitForURL(/\/$|\/customers/, { timeout: 30000, waitUntil: 'domcontentloaded' });

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
  await context.storageState({ path: AUTH_FILE });
  await browser.close();

  console.log(`✅ 已保存登录态: ${AUTH_FILE}`);
}
