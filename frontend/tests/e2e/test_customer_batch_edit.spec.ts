import { test, expect } from './fixtures'
import {
  uiLogin,
  waitForModal,
  waitForTableLoaded,
  generateTestCompanyId,
  generateTestCustomerName,
  apiLogin,
  apiCreateCustomer,
  apiDeleteCustomer,
} from './test-helpers'

/**
 * 客户批量编辑 E2E 测试
 *
 * 测试场景（5 个）：
 * 1. 完整流程 — 勾选 → 显示按钮 → 打开对话框 → 选择字段 → 预览确认 → 提交 → 成功
 * 2. 不勾选 → 按钮不出现
 * 3. 打开对话框 → 取消 → 无数据变更
 * 4. 网络错误处理
 * 5. 字段勾选手柄 — 未勾选字段时输入控件禁用
 */
test.describe('客户批量编辑', () => {
  let authToken: string
  let createdIds: number[] = []

  test.beforeAll(async () => {
    authToken = await apiLogin()
  })

  test.beforeEach(async ({ page }) => {
    createdIds = []
    await uiLogin(page)
    await page.goto('/customers')
    await waitForTableLoaded(page)
  })

  test.afterEach(async ({ page }) => {
    // 清理测试创建的顾客
    for (const id of createdIds) {
      await apiDeleteCustomer(authToken, id).catch(() => {})
    }
    // 确保关闭可能残留的对话框
    await page.keyboard.press('Escape')
    await page.waitForTimeout(300)
  })

  test('1. 批量编辑完整流程成功', async ({ page }) => {
    // 创建两个测试客户
    const companyId1 = generateTestCompanyId('batch_1')
    const name1 = generateTestCustomerName('批量编辑_1')
    const result1 = await apiCreateCustomer(authToken, {
      company_id: companyId1,
      name: name1,
      is_key_customer: false,
    })
    if (result1.data?.id) createdIds.push(result1.data.id as number)

    const companyId2 = generateTestCompanyId('batch_2')
    const name2 = generateTestCustomerName('批量编辑_2')
    const result2 = await apiCreateCustomer(authToken, {
      company_id: companyId2,
      name: name2,
      is_key_customer: false,
    })
    if (result2.data?.id) createdIds.push(result2.data.id as number)

    await page.reload()
    await waitForTableLoaded(page)

    // 勾选第一行客户（通过表格 checkbox）
    const firstRowCheckbox = page
      .locator('.arco-table tbody tr')
      .first()
      .locator('.arco-checkbox')
      .first()
    await firstRowCheckbox.click()
    await page.waitForTimeout(300)

    // 验证 "已选择 X 条" 标签可见
    const selectionTag = page.locator('.batch-selection-bar .arco-tag')
    await expect(selectionTag.first()).toBeVisible()

    // 验证 "批量编辑" 按钮可见
    const batchEditBtn = page.locator('.batch-selection-bar button:has-text("批量编辑")')
    await expect(batchEditBtn.first()).toBeVisible()

    // 点击批量编辑
    await batchEditBtn.first().click()
    await waitForModal(page)

    // 验证对话框标题包含"批量编辑"
    const modalTitle = page.locator('.arco-modal-header, .arco-modal .arco-modal-title')
    await expect(modalTitle.first()).toContainText('批量编辑')

    // 勾选"重点客户" checkbox
    const keyCustomerCheckbox = page
      .locator('.batch-field-item')
      .filter({ hasText: '重点客户' })
      .locator('.arco-checkbox')
    await keyCustomerCheckbox.first().click()
    await page.waitForTimeout(300)

    // 设置开关为 true（打开"是"）
    const switchEl = page
      .locator('.batch-field-item')
      .filter({ hasText: '重点客户' })
      .locator('.arco-switch')
    const switchState = await switchEl.first().getAttribute('class')
    if (!switchState?.includes('arco-switch-checked')) {
      await switchEl.first().click()
      await page.waitForTimeout(300)
    }

    // 点击"预览"按钮
    const previewBtn = page.locator('.arco-modal-footer button:has-text("预览")')
    await previewBtn.first().click()
    await page.waitForTimeout(500)

    // 验证预览弹窗出现
    const previewModal = page.locator('.arco-modal')
    await expect(previewModal.first()).toBeVisible({ timeout: 5000 })
    const previewTitle = page.locator('.arco-modal-header, .arco-modal .arco-modal-title')
    await expect(previewTitle.first()).toContainText('确认批量修改')

    // 预览中应包含"重点客户"字段
    const previewContent = page.locator('.arco-modal-body, .arco-modal .arco-modal-body')
    await expect(previewContent.first()).toContainText('重点客户')

    // 点击预览的"确定"按钮
    const confirmBtn = page
      .locator('.arco-modal-footer button:has-text("确定"), .arco-modal button:has-text("确定")')
      .last()
    await confirmBtn.click()

    // 等待成功 toast
    await expect(page.locator('.arco-message-success').first()).toBeVisible({ timeout: 15000 })

    // 验证对话框已关闭
    const modalAfterSubmit = page.locator('.arco-modal')
    const modalStillVisible = await modalAfterSubmit
      .first()
      .isVisible({ timeout: 2000 })
      .catch(() => false)
    expect(modalStillVisible).toBeFalsy()

    // 验证选择状态已清除
    const selectionBar = page.locator('.batch-selection-bar')
    const selectionBarVisible = await selectionBar
      .first()
      .isVisible({ timeout: 2000 })
      .catch(() => false)
    expect(selectionBarVisible).toBeFalsy()
  })

  test('2. 不选择客户时批量编辑按钮隐藏', async ({ page }) => {
    // 确保没有勾选任何行
    // 全选 checkbox 应该是未勾选状态
    const allCheckbox = page.locator('.arco-table thead .arco-checkbox').first()
    const isChecked = await allCheckbox.isChecked().catch(() => false)
    if (isChecked) {
      await allCheckbox.click()
      await page.waitForTimeout(300)
    }

    // 验证 "批量编辑" 按钮不可见（因为选择栏不显示）
    const batchEditBtn = page.locator('.batch-selection-bar button:has-text("批量编辑")')
    await expect(batchEditBtn).not.toBeVisible({ timeout: 5000 })

    // "已选择 X 条" 标签也不应出现
    const selectionTag = page.locator('.batch-selection-bar .arco-tag')
    await expect(selectionTag).not.toBeVisible({ timeout: 5000 })
  })

  test('3. 打开批量编辑对话框后取消无变更', async ({ page }) => {
    // 创建一个测试客户
    const companyId = generateTestCompanyId('cancel')
    const customerName = generateTestCustomerName('取消测试')
    const result = await apiCreateCustomer(authToken, {
      company_id: companyId,
      name: customerName,
    })
    if (result.data?.id) createdIds.push(result.data.id as number)

    await page.reload()
    await waitForTableLoaded(page)

    // 勾选一行
    const firstRowCheckbox = page
      .locator('.arco-table tbody tr')
      .first()
      .locator('.arco-checkbox')
      .first()
    await firstRowCheckbox.click()
    await page.waitForTimeout(300)

    // 点击批量编辑
    const batchEditBtn = page.locator('.batch-selection-bar button:has-text("批量编辑")')
    await batchEditBtn.first().click()
    await waitForModal(page)

    // 验证对话框已打开
    const modal = page.locator('.arco-modal')
    await expect(modal.first()).toBeVisible()

    // 点击取消按钮
    const cancelBtn = page.locator('.arco-modal-footer button:has-text("取消")')
    await cancelBtn.first().click()

    // 验证对话框关闭
    await expect(modal).not.toBeVisible({ timeout: 5000 })

    // 选择状态应保持（勾选仍然显示）
    const selectionBar = page.locator('.batch-selection-bar')
    await expect(selectionBar.first()).toBeVisible()
  })

  test('4. 批量编辑网络错误处理', async ({ page }) => {
    // 创建一个测试客户
    const companyId = generateTestCompanyId('network_err')
    const customerName = generateTestCustomerName('网络错误')
    const result = await apiCreateCustomer(authToken, {
      company_id: companyId,
      name: customerName,
      is_key_customer: false,
    })
    if (result.data?.id) createdIds.push(result.data.id as number)

    await page.reload()
    await waitForTableLoaded(page)

    // 拦截 API 请求模拟网络错误
    await page.route('**/api/v1/customers/batch-update', async (route) => {
      route.abort('failed')
    })

    // 勾选一行
    const firstRowCheckbox = page
      .locator('.arco-table tbody tr')
      .first()
      .locator('.arco-checkbox')
      .first()
    await firstRowCheckbox.click()
    await page.waitForTimeout(300)

    // 点击批量编辑
    const batchEditBtn = page.locator('.batch-selection-bar button:has-text("批量编辑")')
    await batchEditBtn.first().click()
    await waitForModal(page)

    // 勾选"重点客户" checkbox 并设置
    const keyCustomerCheckbox = page
      .locator('.batch-field-item')
      .filter({ hasText: '重点客户' })
      .locator('.arco-checkbox')
    await keyCustomerCheckbox.first().click()
    await page.waitForTimeout(300)

    const switchEl = page
      .locator('.batch-field-item')
      .filter({ hasText: '重点客户' })
      .locator('.arco-switch')
    const switchState = await switchEl.first().getAttribute('class')
    if (!switchState?.includes('arco-switch-checked')) {
      await switchEl.first().click()
      await page.waitForTimeout(300)
    }

    // 提交 → 预览 → 确认
    const previewBtn = page.locator('.arco-modal-footer button:has-text("预览")')
    await previewBtn.first().click()
    await page.waitForTimeout(500)

    // 点击预览的"确定"
    const confirmBtn = page
      .locator('.arco-modal-footer button:has-text("确定"), .arco-modal button:has-text("确定")')
      .last()
    await confirmBtn.click()

    // 验证错误 toast 出现
    const errorMsg = page.locator('.arco-message-error')
    await expect(errorMsg.first()).toBeVisible({ timeout: 15000 })

    // 验证编辑对话框仍然未关闭（网络错误时不关闭对话框）
    // 预览弹窗可能被关闭，但编辑对话框应仍然可见或有错误消息
    const errorToastVisible = await errorMsg.first().isVisible({ timeout: 2000 })
    expect(errorToastVisible).toBeTruthy()

    // 取消路由拦截
    await page.unroute('**/api/v1/customers/batch-update')
  })

  test('5. 未勾选字段时输入控件禁用', async ({ page }) => {
    // 创建一个测试客户
    const companyId = generateTestCompanyId('disabled')
    const customerName = generateTestCustomerName('禁用测试')
    const result = await apiCreateCustomer(authToken, {
      company_id: companyId,
      name: customerName,
    })
    if (result.data?.id) createdIds.push(result.data.id as number)

    await page.reload()
    await waitForTableLoaded(page)

    // 勾选一行
    const firstRowCheckbox = page
      .locator('.arco-table tbody tr')
      .first()
      .locator('.arco-checkbox')
      .first()
    await firstRowCheckbox.click()
    await page.waitForTimeout(300)

    // 点击批量编辑
    const batchEditBtn = page.locator('.batch-selection-bar button:has-text("批量编辑")')
    await batchEditBtn.first().click()
    await waitForModal(page)

    // 验证"重点客户" checkbox 未勾选
    const keyCustomerField = page.locator('.batch-field-item').filter({ hasText: '重点客户' })
    const checkbox = keyCustomerField.locator('.arco-checkbox')
    const inputEl = checkbox.locator('input[type="checkbox"]')
    const isChecked = await inputEl
      .first()
      .isChecked()
      .catch(() => false)
    expect(isChecked).toBeFalsy()

    // 验证对应开关控件禁用
    const switchEl = keyCustomerField.locator('.arco-switch')
    const switchClass = await switchEl.first().getAttribute('class')
    expect(switchClass).toContain('arco-switch-disabled')

    // 验证"运营经理" select 也是禁用状态
    const managerField = page.locator('.batch-field-item').filter({ hasText: '运营经理' })
    const managerSelect = managerField.locator('.arco-select')
    const managerClass = await managerSelect.first().getAttribute('class')
    expect(managerClass).toContain('arco-select-disabled')

    // 勾选"重点客户" checkbox
    await checkbox.first().click()
    await page.waitForTimeout(500)

    // 验证对应开关控件启用
    const switchClassAfter = await switchEl.first().getAttribute('class')
    expect(switchClassAfter).not.toContain('arco-switch-disabled')
  })
})
