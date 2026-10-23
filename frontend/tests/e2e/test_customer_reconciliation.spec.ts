import { test, expect } from './fixtures'
import type { Page } from '@playwright/test'
import {
  uiLogin,
  waitForModal,
  fillFormField,
  generateTestCompanyId,
  generateTestCustomerName,
  apiLogin,
  apiDeleteCustomer,
  apiGetCustomers,
} from './test-helpers'

/**
 * 客户「是否对账」属性 E2E 测试
 *
 * 覆盖需求：
 * - 表单渲染「是否对账」字段（label/选项/默认否）
 * - 开对账=是 + 不填经理 → 前端 required 拦截提交
 * - 开对账=是 + 填齐经理 → 创建成功（require_reconciliation=True）
 * - 开对账=否 + 不填经理 → 创建成功（require_reconciliation=False）
 */

/** 选择「是否对账」的值（Arco select：点开下拉后点选项） */
async function selectReconciliation(page: Page, value: '是' | '否') {
  const modal = page.locator('.arco-modal:visible')
  const item = modal.locator('.arco-form-item', { has: page.locator('text=是否对账') }).last()
  await item.locator('.arco-select-view').click()
  const dropdown = page.locator('.arco-select-dropdown:visible').last()
  await dropdown.locator('.arco-select-option', { hasText: value }).first().click()
}

/** 读取「是否对账」当前显示值 */
async function readReconciliationValue(page: Page): Promise<string | null> {
  const modal = page.locator('.arco-modal:visible')
  const item = modal.locator('.arco-form-item', { has: page.locator('text=是否对账') }).last()
  const v = item.locator('.arco-select-view-value')
  if ((await v.count()) === 0) return null
  return (await v.first().innerText()).trim()
}

test.describe('客户「是否对账」属性 @reconciliation', () => {
  let authToken: string

  test.beforeAll(async () => {
    authToken = await apiLogin()
  })

  test.beforeEach(async ({ page }) => {
    await uiLogin(page)
    await page.goto('/customers')
  })

  test('1. 新增客户表单渲染「是否对账」且默认否', async ({ page }) => {
    await page.locator('button:has-text("新增客户")').first().click()
    await waitForModal(page)

    const modal = page.locator('.arco-modal:visible')
    // label 存在，旧字段名不存在
    await expect(modal.locator('text=是否对账').first()).toBeVisible()
    await expect(modal.locator('text=自动发起结算')).toHaveCount(0)

    // 默认值 = 否
    const value = await readReconciliationValue(page)
    expect(value).toBe('否')
  })

  test('2. 开对账=是但不填经理 → 前端 required 拦截', async ({ page }) => {
    const companyId = generateTestCompanyId()
    const customerName = generateTestCustomerName()

    await page.locator('button:has-text("新增客户")').first().click()
    await waitForModal(page)

    await fillFormField(page, '客户ID', String(companyId))
    await fillFormField(page, '客户名称', customerName)
    await selectReconciliation(page, '是')
    expect(await readReconciliationValue(page)).toBe('是')

    // 提交 → 应被拦截，弹窗不关闭
    const modal = page.locator('.arco-modal:visible')
    await modal.locator('.arco-modal-footer button', { hasText: '确定' }).click()

    // 弹窗仍在 + 经理字段出现必填错误
    await expect(modal).toBeVisible()
    const mgrItem = modal.locator('.arco-form-item', { has: page.locator('text=运营经理') }).last()
    await expect(mgrItem.locator('.arco-form-item-message')).toHaveCount(1)
    const msg = await mgrItem.locator('.arco-form-item-message').first().innerText()
    expect(msg).toContain('开启对账后必填')

    // 未创建客户
    const list = await apiGetCustomers(authToken, `keyword=${encodeURIComponent(customerName)}`)
    const items =
      ((list.data as Record<string, unknown>).list as Array<Record<string, unknown>>) || []
    expect(items.length).toBe(0)
  })

  test('3. 开对账=是且填齐经理 → 创建成功', async ({ page }) => {
    const companyId = generateTestCompanyId()
    const customerName = generateTestCustomerName()

    await page.locator('button:has-text("新增客户")').first().click()
    await waitForModal(page)

    await fillFormField(page, '客户ID', String(companyId))
    await fillFormField(page, '客户名称', customerName)
    await selectReconciliation(page, '是')

    const modal = page.locator('.arco-modal:visible')
    // 选择运营经理 / 商务经理（取下拉第一个选项）
    for (const label of ['运营经理', '商务经理']) {
      const item = modal.locator('.arco-form-item', { has: page.locator(`text=${label}`) }).last()
      await item.locator('.arco-select-view').click()
      const dropdown = page.locator('.arco-select-dropdown:visible').last()
      await dropdown.locator('.arco-select-option').first().click()
    }

    await modal.locator('.arco-modal-footer button', { hasText: '确定' }).click()

    // 弹窗关闭 = 前端校验通过并提交成功
    await expect(page.locator('.arco-modal:visible')).toHaveCount(0, { timeout: 10000 })
    await expect(page.locator('.arco-message-success')).toBeVisible({ timeout: 10000 })

    // 校验落库值
    const list = await apiGetCustomers(authToken, `keyword=${encodeURIComponent(customerName)}`)
    const items =
      ((list.data as Record<string, unknown>).list as Array<Record<string, unknown>>) || []
    expect(items.length).toBe(1)
    expect(items[0].require_reconciliation).toBe(true)

    // 清理
    await apiDeleteCustomer(authToken, Number(items[0].id))
  })

  test('4. 开对账=否且不填经理 → 创建成功', async ({ page }) => {
    const companyId = generateTestCompanyId()
    const customerName = generateTestCustomerName()

    await page.locator('button:has-text("新增客户")').first().click()
    await waitForModal(page)

    await fillFormField(page, '客户ID', String(companyId))
    await fillFormField(page, '客户名称', customerName)
    // 默认即否，无需切换
    expect(await readReconciliationValue(page)).toBe('否')

    const modal = page.locator('.arco-modal:visible')
    await modal.locator('.arco-modal-footer button', { hasText: '确定' }).click()

    await expect(page.locator('.arco-modal:visible')).toHaveCount(0, { timeout: 10000 })
    await expect(page.locator('.arco-message-success')).toBeVisible({ timeout: 10000 })

    const list = await apiGetCustomers(authToken, `keyword=${encodeURIComponent(customerName)}`)
    const items =
      ((list.data as Record<string, unknown>).list as Array<Record<string, unknown>>) || []
    expect(items.length).toBe(1)
    expect(items[0].require_reconciliation).toBe(false)

    // 清理
    await apiDeleteCustomer(authToken, Number(items[0].id))
  })
})
