import { chromium, type FullConfig } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'node:url'

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
 * 公告弹窗隔离：Dashboard 是 `/` 布局父组件，customers / billing 等所有需登录路由
 * 都是它的 children，故其 onMounted 的公告请求在每个页面都会触发。公告弹窗
 * mask-closable=false 的全屏遮罩会拦截页面所有指针事件。E2E 只关心业务链路，故
 * 按组件的「用户 × 浏览器」已读口径预写 localStorage 键并随 storageState 一并复用，
 * 使各用例从源头不再被公告遮挡（比「等弹窗出现再点关闭」更快且无时序窗口）。
 *
 * 注意：frontend/package.json 为 `"type": "module"`，故用 fileURLToPath 取目录
 * （ESM 下没有 __dirname）。
 */
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const AUTH_FILE = path.join(__dirname, '.auth', 'admin.json')

export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0]?.use?.baseURL ?? 'http://localhost:5173'

  const browser = await chromium.launch()
  const context = await browser.newContext()
  const page = await context.newPage()

  await page.goto(`${baseURL}/login`, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('input[field="username"], input[type="text"]', { timeout: 15000 })
  await page.fill('input[field="username"], input[type="text"]', 'admin')
  await page.fill('input[field="password"], input[type="password"]', 'admin123')
  await page.click('button[type="submit"], button:has-text("登录")')
  await page.waitForURL(/\/$|\/customers/, { timeout: 30000, waitUntil: 'domcontentloaded' })

  // 预写公告「已读」键：Dashboard 是 `/` 布局父组件，所有需登录路由都会触发其公告
  // 请求；弹窗 mask-closable=false 的全屏遮罩会拦截页面所有指针事件。E2E 不关心
  // 公告本身，故在此写入「已读」localStorage 并随 storageState 一并复用，使各用例
  // 从源头不再弹窗（比「等弹窗出现再点关闭」更快且无时序窗口）。
  await page.evaluate(() => {
    const raw = localStorage.getItem('user_info')
    if (!raw) return
    let uid: number | undefined
    try {
      const parsed: unknown = JSON.parse(raw)
      if (parsed !== null && typeof parsed === 'object' && 'id' in parsed) {
        const id: unknown = parsed.id
        if (typeof id === 'number') uid = id
      }
    } catch {
      return
    }
    if (uid === undefined) return
    // 9999 年：任何真实部署时间词法上都小于它
    localStorage.setItem(`upgrade_announcement_last_read_${uid}`, '9999-12-31T23:59:59Z')
  })
  console.log('✅ 已预写公告已读键（抑制系统升级公告弹窗）')

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true })
  await context.storageState({ path: AUTH_FILE })
  await browser.close()

  console.log(`✅ 已保存登录态: ${AUTH_FILE}`)
}
