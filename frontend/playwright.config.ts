import { defineConfig, devices } from '@playwright/test';

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
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'tests/e2e/playwright-report' }],
    ['list'],
  ],
  use: {
    baseURL: 'http://localhost:5173',
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
      use: { ...devices['Pixel 5'] },
    },
  ],
  outputDir: 'tests/e2e/test-results',
});
