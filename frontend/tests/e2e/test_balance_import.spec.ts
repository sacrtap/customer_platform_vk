import { test, expect } from './fixtures'
import {
  uiLogin,
  waitForTableLoaded,
  waitForModal,
  getVisibleModal,
  apiLogin,
} from './test-helpers'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

/**
 * 余额导入 E2E 测试
 */
test.describe('余额导入', () => {
  let authToken: string
  const tempDir = os.tmpdir()

  test.beforeAll(async () => {
    authToken = await apiLogin()
  })

  test.beforeEach(async ({ page }) => {
    await uiLogin(page)
    await page.goto('/billing/balances')
    await waitForTableLoaded(page)
  })

  test('1. 导入按钮可见且可点击', async ({ page }) => {
    // 验证导入按钮存在（按钮文本为“导入”）
    const importButton = page.getByRole('button', { name: '导入' })
    await expect(importButton).toBeVisible()

    // 点击按钮打开对话框
    await importButton.click()

    // 验证对话框打开
    await waitForModal(page)
    await expect(
      page.locator('.arco-modal-title').filter({ hasText: /批量导入充值/i })
    ).toBeVisible()
  })

  test('2. 导入对话框包含下载模板按钮和上传区域', async ({ page }) => {
    // 打开导入对话框
    await page.getByRole('button', { name: '导入' }).click()
    await waitForModal(page)

    // 验证 modal 标题
    await expect(
      page.locator('.arco-modal-title').filter({ hasText: /批量导入充值/i })
    ).toBeVisible()

    // 验证“下载模板”按钮存在（在 a-alert 的 action 插槽中）
    await expect(
      page.locator('.arco-modal-body').getByRole('button', { name: /下载模板/i })
    ).toBeVisible()

    // 验证自定义上传区域存在
    await expect(page.locator('.upload-area')).toBeVisible()

    // 验证提示信息（两步导入：预检查 → 确认导入，文案随 ImportBalanceModal 改版）
    await expect(page.locator('.arco-modal-body').getByText(/请选择文件进行导入/)).toBeVisible()

    // 验证两步导入按钮存在
    await expect(
      page.locator('.arco-modal-body').getByRole('button', { name: /预检查/i })
    ).toBeVisible()
    await expect(
      page.locator('.arco-modal-body').getByRole('button', { name: /确认导入/i })
    ).toBeVisible()
  })

  test('3. 上传文件并导入', async ({ page }) => {
    // 先获取一个存在的客户
    const customersResponse = await page.request.get('http://localhost:8000/api/v1/customers', {
      headers: { Authorization: `Bearer ${authToken}` },
      params: { page: 1, page_size: 1 },
    })
    const customersData = await customersResponse.json()

    if (!customersData.data?.list || customersData.data.list.length === 0) {
      test.skip()
      return
    }

    // 打开导入对话框
    await page.getByRole('button', { name: '导入' }).click()
    await waitForModal(page)

    // 通过 API 下载模板
    const templatePath = path.join(tempDir, 'balance_import_test.xlsx')
    const templateResponse = await page.request.get(
      'http://localhost:8000/api/v1/billing/import-template',
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    )
    const templateBuffer = await templateResponse.body()
    fs.writeFileSync(templatePath, templateBuffer)

    // 上传文件（使用隐藏的 file input）
    const fileInput = page.locator('.arco-modal-body input[type="file"]')
    await fileInput.setInputFiles(templatePath)

    // 验证文件已选择（自定义文件卡片）
    await expect(page.locator('.file-selected')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('.file-name')).toContainText('balance_import_test.xlsx')

    // 两步导入：先预检查（不落库），再确认导入
    await page.getByRole('button', { name: /预检查/i }).click()
    await expect(
      page
        .locator('.arco-modal-body')
        .getByText(/预检查结果/)
        .first()
    ).toBeVisible({ timeout: 10000 })

    await page.getByRole('button', { name: /确认导入/i }).click()

    // 等待导入结果
    await page.waitForTimeout(3000)

    // 验证有某种反馈（导入结果以全局 message 提示呈现，不限于 modal 内）
    const hasResult = await page
      .getByText(/导入成功|导入完成|导入失败/)
      .first()
      .isVisible({ timeout: 10000 })
      .catch(() => false)
    expect(hasResult).toBeTruthy()

    // 清理
    if (fs.existsSync(templatePath)) {
      fs.unlinkSync(templatePath)
    }
  })

  test('4. 导入对话框可关闭', async ({ page }) => {
    // 打开导入对话框
    await page.getByRole('button', { name: '导入' }).click()
    await waitForModal(page)

    // 两步导入版弹窗无底部「取消」按钮（footer=false），右上角关闭 X 是唯一关闭途径。
    // 页面存在多个 modal 实例（余额充值等），close-btn 需限定在可见 modal 内
    await getVisibleModal(page).locator('.arco-modal-close-btn').click()

    // 验证对话框关闭
    await expect(
      page.locator('.arco-modal-title').filter({ hasText: /批量导入充值/i })
    ).not.toBeVisible({ timeout: 5000 })
  })

  test('5. 未选择文件时预检查按钮禁用', async ({ page }) => {
    // 打开导入对话框
    await page.getByRole('button', { name: '导入' }).click()
    await waitForModal(page)

    // 未上传文件时「预检查」禁用，无法发起导入流程（两步导入语义：选文件后才能预检查）
    await expect(
      page.locator('.arco-modal-body').getByRole('button', { name: /预检查/i })
    ).toBeDisabled()
  })
})
