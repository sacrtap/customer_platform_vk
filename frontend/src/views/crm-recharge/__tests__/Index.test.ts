import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList
}

const pushMock = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push: pushMock }) }))

const hasPermissionMock = vi.fn(() => true)
vi.mock('@/stores/user', () => ({
  useUserStore: () => ({ hasPermission: hasPermissionMock }),
}))

const payment = {
  id: 11,
  external_id: 900101,
  crm_customer_id: 1,
  crm_customer_name: '验收宜家家居',
  contract_external_id: 7001,
  contract_title: '宜家年度框架',
  amount: '1200.50',
  receive_date: '2026-11-05',
  approve_status: 'approved',
  industry_path: '1001/二手房',
  industry_label: '房产经纪/二手房',
  eligible: true,
  blocked_reason: null,
  source_changed: false,
  status: 'pending' as const,
  bound_customer_id: 7,
  bound_customer_name: '宜家',
  bound_company_id: '7',
  last_seen_at: null,
  recharge_record_id: null,
  real_amount: null,
  bonus_amount: null,
  total_amount: null,
  recharge_date: null,
  recharge_created_at: null,
}

const getCrmPaymentsMock = vi.fn()
const getCrmSyncRunsMock = vi.fn().mockResolvedValue({
  data: { list: [], total: 0, page: 1, page_size: 1, latest_success_at: null },
})
const importCrmPaymentMock = vi.fn()
const revokeCrmImportMock = vi.fn()
const createCrmSyncRunMock = vi.fn()
const getCrmSettingsMock = vi.fn()
const testCrmCredentialsMock = vi.fn()
const updateCrmSettingsMock = vi.fn()

vi.mock('@/api/customers', () => ({
  getCustomers: vi.fn().mockResolvedValue({ data: { list: [] } }),
}))

vi.mock('@/api/crmRecharge', () => ({
  getCrmPayments: (...args: unknown[]) => getCrmPaymentsMock(...args),
  getCrmSyncRuns: (...args: unknown[]) => getCrmSyncRunsMock(...args),
  importCrmPayment: (...args: unknown[]) => importCrmPaymentMock(...args),
  revokeCrmImport: (...args: unknown[]) => revokeCrmImportMock(...args),
  createCrmSyncRun: (...args: unknown[]) => createCrmSyncRunMock(...args),
  getCrmSettings: (...args: unknown[]) => getCrmSettingsMock(...args),
  testCrmCredentials: (...args: unknown[]) => testCrmCredentialsMock(...args),
  updateCrmSettings: (...args: unknown[]) => updateCrmSettingsMock(...args),
}))

const settingsData = {
  enabled: true,
  base_url: 'https://lxcrm.weiwenjia.com',
  corp_id: 'corp-1',
  phone_masked: '138****1111',
  password_set: true,
  credentials_complete: true,
  active: true,
  source: 'database' as const,
  credential_key_configured: true,
  crm_enabled_for_requests: true,
}

const findButton = (text: string): HTMLButtonElement | undefined =>
  Array.from(document.querySelectorAll<HTMLButtonElement>('button')).find((b) =>
    b.textContent?.trim().includes(text)
  )

const setInput = async (selector: string, value: string) => {
  const el = document.querySelector<HTMLInputElement>(selector)
  if (!el) throw new Error(`input not found: ${selector}`)
  el.value = value
  el.dispatchEvent(new Event('input'))
  await flush()
}

const flush = async () => {
  await flushPromises()
  await nextTick()
}

import CrmRecharge from '@/views/crm-recharge/Index.vue'

describe('CrmRecharge Index', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    hasPermissionMock.mockReturnValue(true)
    getCrmSettingsMock.mockResolvedValue({ data: settingsData })
    getCrmPaymentsMock.mockResolvedValue({
      data: { list: [payment], total: 1, page: 1, page_size: 20, crm_enabled: false },
    })
  })

  const mountPage = async () => {
    const wrapper = mount(CrmRecharge, { global: { plugins: [ArcoVue] } })
    await flush()
    return wrapper
  }

  it('渲染回款行并显示待导入状态与绑定客户', async () => {
    const wrapper = await mountPage()
    const text = wrapper.text()
    expect(text).toContain('#900101')
    expect(text).toContain('验收宜家家居')
    expect(text).toContain('待导入')
    expect(text).toContain('宜家')
    expect(getCrmPaymentsMock).toHaveBeenCalled()
  })

  it('CRM 未启用时按钮仍可点击，点击导入给出明确原因', async () => {
    const wrapper = await mountPage()
    // 按钮不得被禁用：用户点下去必须得到反馈，而不是死按钮
    const sync = wrapper.findAll('button').find((b) => b.text().includes('同步CRM回款'))
    const importBtn = wrapper.findAll('button').find((b) => b.text().trim() === '导入充值')
    expect(sync?.attributes('disabled')).toBeUndefined()
    expect(importBtn?.attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('当前 CRM 未启用')

    await importBtn!.trigger('click')
    await flush()
    expect(document.body.textContent).toContain('CRM 未启用')
    expect(document.body.textContent).not.toContain('实充金额')
  })

  it('CRM 未启用时同步弹窗打开并说明缺少什么配置', async () => {
    const wrapper = await mountPage()
    const sync = wrapper.findAll('button').find((b) => b.text().includes('同步CRM回款'))
    await sync!.trigger('click')
    await flush()
    expect(document.body.textContent).toContain('CRM 配置')
  })

  it('CRM 启用后导入按钮带出实充金额', async () => {
    getCrmPaymentsMock.mockResolvedValue({
      data: { list: [payment], total: 1, page: 1, page_size: 20, crm_enabled: true },
    })
    const wrapper = await mountPage()
    const importBtn = wrapper.findAll('button').find((b) => b.text().trim() === '导入充值')

    await importBtn!.trigger('click')
    await flush()
    // a-modal 传送到 body，断言文档内容而非组件根节点
    expect(document.body.textContent).toContain('实充金额')
    expect(document.body.textContent).toContain('¥1,200.50')
  })

  it('打开 CRM 配置弹窗并展示配置来源与打码手机号', async () => {
    const wrapper = await mountPage()
    await wrapper
      .findAll('button')
      .find((b) => b.text().includes('CRM 配置'))!
      .trigger('click')
    await flush()

    expect(getCrmSettingsMock).toHaveBeenCalled()
    expect(document.body.textContent).toContain('页面保存的配置')
    expect(document.body.textContent).toContain('138****1111')
    expect(document.body.textContent).toContain('密码：已配置')
  })

  it('验证账号密码：使用表单里的新凭据并展示可见客户数', async () => {
    testCrmCredentialsMock.mockResolvedValue({ data: { ok: true, customer_total: 5032 } })
    const wrapper = await mountPage()
    await wrapper
      .findAll('button')
      .find((b) => b.text().includes('CRM 配置'))!
      .trigger('click')
    await flush()

    await setInput('input[placeholder="CRM 登录账号手机号"]', '13900002222')
    await setInput('input[placeholder="已配置，留空则不修改"]', 'NewPass!1')
    findButton('验证账号密码')!.click()
    await flush()

    const payload = testCrmCredentialsMock.mock.calls[0][0] as Record<string, unknown>
    expect(payload.phone).toBe('13900002222')
    expect(payload.password).toBe('NewPass!1')
    expect(document.body.textContent).toContain('该账号可访问 5032 位 CRM 客户')
  })

  it('验证失败时展示后端返回的具体原因', async () => {
    testCrmCredentialsMock.mockRejectedValue({
      code: 40001,
      message: 'CRM 登录失败：账号或密码不正确',
    })
    const wrapper = await mountPage()
    await wrapper
      .findAll('button')
      .find((b) => b.text().includes('CRM 配置'))!
      .trigger('click')
    await flush()

    await setInput('input[placeholder="CRM 登录账号手机号"]', '13900002222')
    await setInput('input[placeholder="已配置，留空则不修改"]', 'bad')
    findButton('验证账号密码')!.click()
    await flush()

    expect(document.body.textContent).toContain('CRM 登录失败：账号或密码不正确')
  })

  it('保存成功提示已验证客户数并关闭弹窗', async () => {
    updateCrmSettingsMock.mockResolvedValue({
      data: { ...settingsData, verified_customer_total: 5032 },
    })
    const wrapper = await mountPage()
    await wrapper
      .findAll('button')
      .find((b) => b.text().includes('CRM 配置'))!
      .trigger('click')
    await flush()

    await setInput('input[placeholder="CRM 登录账号手机号"]', '13900002222')
    findButton('保存配置')!.click()
    await flush()

    const payload = updateCrmSettingsMock.mock.calls[0][0] as Record<string, unknown>
    expect(payload.phone).toBe('13900002222')
    expect(payload.force).toBeUndefined()
    expect(document.body.textContent).toContain('CRM 配置已保存并验证通过（可访问 5032 位客户）')
  })

  it('保存前验证失败时要求二次确认，确认后以 force 强制保存', async () => {
    updateCrmSettingsMock.mockRejectedValueOnce({
      code: 42201,
      message: 'CRM 登录失败：账号或密码不正确',
    })
    updateCrmSettingsMock.mockResolvedValueOnce({ data: settingsData })

    const wrapper = await mountPage()
    await wrapper
      .findAll('button')
      .find((b) => b.text().includes('CRM 配置'))!
      .trigger('click')
    await flush()

    await setInput('input[placeholder="CRM 登录账号手机号"]', '13900002222')
    findButton('保存配置')!.click()
    await flush()

    expect(document.body.textContent).toContain('验证未通过，仍要保存吗？')
    const confirmBtn = findButton('仍然保存')
    expect(confirmBtn).toBeTruthy()
    confirmBtn!.click()
    await flush()

    const secondPayload = updateCrmSettingsMock.mock.calls[1][0] as Record<string, unknown>
    expect(secondPayload.force).toBe(true)
  })

  it('勾选清除密码后保存不需要填密码，并携带 clear_password', async () => {
    updateCrmSettingsMock.mockResolvedValue({
      data: { ...settingsData, password_set: false, credentials_complete: false, active: false },
    })
    const wrapper = await mountPage()
    await wrapper
      .findAll('button')
      .find((b) => b.text().includes('CRM 配置'))!
      .trigger('click')
    await flush()

    const checkbox = document.querySelector('.arco-checkbox') as HTMLElement | null
    expect(checkbox).toBeTruthy()
    checkbox!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flush()

    findButton('保存配置')!.click()
    await flush()

    const payload = updateCrmSettingsMock.mock.calls[0][0] as Record<string, unknown>
    expect(payload.clear_password).toBe(true)
    expect(payload.password).toBeUndefined()
  })

  it('凭据有效但客户列表不可读时给出降级说明而不是判失败', async () => {
    testCrmCredentialsMock.mockResolvedValue({
      data: {
        ok: true,
        customer_total: null,
        warning: 'CRM 分页响应缺少列表字段（data 键：total_count）',
      },
    })
    const wrapper = await mountPage()
    await wrapper
      .findAll('button')
      .find((b) => b.text().includes('CRM 配置'))!
      .trigger('click')
    await flush()

    await setInput('input[placeholder="CRM 登录账号手机号"]', '13900002222')
    findButton('验证账号密码')!.click()
    await flush()

    expect(document.body.textContent).toContain('登录凭据有效')
    expect(document.body.textContent).toContain('客户列表读取失败')
    expect(document.body.textContent).toContain('缺少列表字段')
  })

  it('手动同步后列表页立即显示执行状态，避免用户看不到进度', async () => {
    getCrmPaymentsMock.mockResolvedValue({
      data: { list: [payment], total: 1, page: 1, page_size: 20, crm_enabled: true },
    })
    createCrmSyncRunMock.mockResolvedValue({
      data: { code: 0, message: '同步任务已创建', data: { id: 77, status: 'pending' } },
    })
    // 第一次为挂载时的状态读取（无任务），第二次为创建任务后的回读（执行中）
    getCrmSyncRunsMock
      .mockResolvedValueOnce({
        data: { list: [], total: 0, page: 1, page_size: 5, latest_success_at: null },
      })
      .mockResolvedValueOnce({
        data: {
          list: [
            {
              id: 77,
              month: '2026-11-01',
              trigger: 'manual',
              status: 'running',
              phase: 'payments',
              customer_count: 5032,
              contract_count: 0,
              scanned_contract_count: 0,
              scanned_payment_count: 600,
              payment_count: 3,
              eligible_count: 3,
              started_at: null,
              finished_at: null,
              heartbeat_at: null,
              error_message: null,
            },
          ],
          total: 1,
          page: 1,
          page_size: 5,
          latest_success_at: null,
        },
      })

    const wrapper = await mountPage()
    const sync = wrapper.findAll('button').find((b) => b.text().includes('同步CRM回款'))
    await sync!.trigger('click')
    await flush()

    findButton('开始同步')!.click()
    await flush()

    // 列表页常驻状态：任务号 + 阶段 + 实时计数
    expect(document.body.textContent).toContain('任务 #77')
    expect(document.body.textContent).toContain('拉取回款列表')
    expect(document.body.textContent).toContain('已检查 600 笔回款')
    expect(getCrmSyncRunsMock.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('已导入的回款可撤销：原因必填，提交后带 customer_id 与 force', async () => {
    getCrmPaymentsMock.mockResolvedValue({
      data: {
        list: [
          {
            ...payment,
            status: 'imported',
            real_amount: '1200.50',
            bonus_amount: '100.00',
            total_amount: '1300.50',
            recharge_record_id: 4662,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
        crm_enabled: true,
      },
    })
    revokeCrmImportMock.mockResolvedValue({ data: { message: '已撤销CRM充值导入' } })

    const wrapper = await mountPage()
    const revokeBtn = wrapper.findAll('button').find((b) => b.text().includes('撤销导入'))
    expect(revokeBtn).toBeTruthy()
    await revokeBtn!.trigger('click')
    await flush()

    expect(document.body.textContent).toContain('撤销会立即扣回该笔')

    // 未填原因不提交
    findButton('确认撤销')!.click()
    await flush()
    expect(revokeCrmImportMock).not.toHaveBeenCalled()

    const reason = document.querySelector<HTMLTextAreaElement>('.arco-modal textarea')
    expect(reason).toBeTruthy()
    reason!.value = 'CRM客户绑定错误'
    reason!.dispatchEvent(new Event('input'))
    await flush()

    findButton('确认撤销')!.click()
    await flush()

    expect(revokeCrmImportMock).toHaveBeenCalledWith(11, {
      customer_id: 7,
      reason: 'CRM客户绑定错误',
      force: false,
    })
  })

  it('运行中显示中文阶段与合同扫描进度，避免长时间同步被当成卡死', async () => {
    getCrmSyncRunsMock.mockResolvedValueOnce({
      data: {
        list: [
          {
            id: 42,
            month: '2026-11-01',
            trigger: 'manual',
            status: 'running',
            phase: 'contracts',
            customer_count: 5032,
            contract_count: 150,
            scanned_contract_count: 150,
            payment_count: 0,
            eligible_count: 0,
            started_at: null,
            finished_at: null,
            error_message: null,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
        latest_success_at: null,
      },
    })
    const wrapper = await mountPage()
    const sync = wrapper.findAll('button').find((b) => b.text().includes('同步CRM回款'))
    await sync!.trigger('click')
    await flush()

    expect(document.body.textContent).toContain('扫描合同与回款')
    expect(document.body.textContent).toContain('已扫描 150 个合同')
  })
})
