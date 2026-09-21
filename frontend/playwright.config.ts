import { defineConfig, devices } from '@playwright/test'
import * as path from 'path'
import { fileURLToPath } from 'node:url'

// frontend/package.json 为 "type": "module"，ESM 下没有 __dirname
const __dirname = path.dirname(fileURLToPath(import.meta.url))

/**
 * Playwright 测试配置
 *
 * 运行测试:
 * - npx playwright test              # 运行所有测试
 * - npx playwright test --ui         # UI 模式
 * - npx playwright test --project=chromium  # 仅 Chromium
 * - npx playwright test --headed     # 有头模式 (显示浏览器)
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? parseInt(process.env.PLAYWRIGHT_WORKERS || '3') || 3 : undefined,
  timeout: 60000,
  expect: {
    timeout: 15000,
    toHaveScreenshot: {
      // 视觉回归测试基线截图不区分平台（不含 {platform}），避免 macOS(darwin) 与 CI Linux 基线不匹配；
      // 但保留 {projectName} 以匹配仓库既有基线命名（如 home-chromium.png）
      pathTemplate: '{snapshotDir}/{testFileDir}/{testFileName}-snapshots/{arg}-{projectName}{ext}',
      // 搭配 maxDiffPixelRatio 容忍跨平台字体渲染差异
      maxDiffPixelRatio: 0.1,
    },
  },
  reporter: [['html', { outputFolder: 'tests/e2e/playwright-report' }], ['list']],
  // 全局登录一次并写入 storageState，供所有用例复用（见 tests/e2e/global-setup.ts）。
  // 每个用例单独 UI 登录约需 2-3 秒，此前 27/34 个文件在 beforeEach 中重复登录。
  // 需要「未登录」状态的测试用 test.use({ storageState: { cookies: [], origins: [] } }) 覆盖。
  globalSetup: path.join(__dirname, 'tests/e2e/global-setup.ts'),
  use: {
    baseURL: 'http://localhost:5173',
    storageState: path.join(__dirname, 'tests/e2e/.auth/admin.json'),
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'Mobile Chrome',
      timeout: 60000, // 增加超时时间到 60s（Project 级属性）
      use: {
        ...devices['Pixel 5'],
      },
    },
  ],
  outputDir: 'tests/e2e/test-results',
})
