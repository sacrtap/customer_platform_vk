import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, enableAutoUnmount, type VueWrapper } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import { nextTick } from 'vue'
import EditCustomerDialog from '@/views/customers/detail/EditCustomerDialog.vue'

// 避免 jsdom 卸载后残留 rAF
enableAutoUnmount(afterEach)
// jsdom 缺少 window.matchMedia，Arco a-modal/a-grid 的响应式监听会调用它，
// 不 polyfill 会抛「window.matchMedia is not a function」并吞掉 watch 回调。
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

// ---- mock 依赖（全部返回已 resolve 的 promise，微任务即完成）----
const updateCustomerMock = vi.fn().mockResolvedValue({ data: { id: 1 } })
const getCustomerMock = vi.fn().mockResolvedValue({
  data: {
    data: {
      id: 1,
      company_id: 1001,
      name: '测试客户',
      email: '',
      account_type: undefined,
      profile: { industry_type_id: null, scale_level: undefined, consume_level: undefined },
      price_policy: undefined,
      settlement_type: 'prepaid',
      settlement_cycle: undefined,
      is_key_customer: false,
      // 初始有运营/销售经理
      manager_id: 5,
      sales_manager_id: 7,
      erp_system: undefined,
      first_payment_date: undefined,
      onboarding_date: undefined,
      cooperation_status: undefined,
      is_settlement_enabled: true,
      require_reconciliation: false,
      is_disabled: false,
      notes: undefined,
      is_real_estate: null,
      settlement_account_id: undefined,
      settlement_account_name: null,
    },
  },
})
const getIndustryTypesMock = vi.fn().mockResolvedValue({ data: { data: [] } })
const getCooperationStatusesListMock = vi.fn().mockResolvedValue({ data: { data: [] } })
const getErpSystemsListMock = vi.fn().mockResolvedValue({ data: { data: [] } })
const getManagersMock = vi.fn().mockResolvedValue({ data: { list: [] } })

vi.mock('@/api/customers', () => ({
  getCustomer: (...args: unknown[]) => getCustomerMock(...args),
  updateCustomer: (...args: unknown[]) => updateCustomerMock(...args),
  getIndustryTypes: () => getIndustryTypesMock(),
}))
vi.mock('@/api/cooperationStatuses', () => ({
  getCooperationStatusesList: () => getCooperationStatusesListMock(),
}))
vi.mock('@/api/erpSystems', () => ({
  getErpSystemsList: () => getErpSystemsListMock(),
}))
vi.mock('@/api/users', () => ({
  getManagers: () => getManagersMock(),
}))

// CustomerAutoComplete 是复杂组件，mock 成存根
vi.mock('@/components/CustomerAutoComplete.vue', () => ({
  default: {
    name: 'CustomerAutoComplete',
    template: '<div class="customer-autocomplete-stub" />',
  },
}))

interface EditFormVM {
  editForm: { manager_id: number | undefined; sales_manager_id: number | undefined }
  fetchLoading: boolean
  handleSubmit: () => Promise<void>
}

// 刷新微任务直到「真实信号」出现：fetchAndInitForm 完成会把 fetchLoading 置 false。
// 仅用微任务刷新，不引入真实计时器；信号未出现则有限次数后失败，指向真正原因。
async function waitForInit(wrapper: VueWrapper): Promise<EditFormVM> {
  const vm = wrapper.vm as unknown as EditFormVM
  let tries = 0
  while (vm.fetchLoading && tries < 100) {
    await Promise.resolve()
    tries++
  }
  await nextTick()
  return vm
}

async function mountDialog() {
  const wrapper = mount(EditCustomerDialog, {
    global: {
      plugins: [ArcoVue],
      stubs: { ATooltip: true },
    },
    props: {
      // watch 非 immediate：初始 visible=false，再切 true 触发 fetchAndInitForm
      visible: false,
      customerId: 1,
      managers: [
        { id: 5, real_name: '运营-张三' },
        { id: 7, real_name: '商务-李四' },
      ],
    },
  })
  await nextTick()
  await wrapper.setProps({ visible: true })
  const vm = await waitForInit(wrapper)
  return { wrapper, vm }
}

describe('EditCustomerDialog — 删除经理后保存', () => {
  beforeEach(() => {
    updateCustomerMock.mockClear()
    getCustomerMock.mockClear()
  })
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('删除运营/销售经理后，payload 携带 manager_id=null 以清空（Arco allow-clear emit ""）', async () => {
    const { vm } = await mountDialog()

    expect(vm.editForm.manager_id).toBe(5)
    // 模拟 Arco a-select allow-clear 的真实行为：清空选中 emit 空字符串 ""，
    // 而非 undefined/null（见 select.js getValueFromValueKeys：无空串 option 时返回 ""）。
    // "" 是 falsy 但 ?? null 捕获不到（"" ?? null === ""），必须用 || null 归一。
    vm.editForm.manager_id = '' as unknown as number
    vm.editForm.sales_manager_id = '' as unknown as number
    await nextTick()

    await vm.handleSubmit()

    expect(updateCustomerMock).toHaveBeenCalledTimes(1)
    const payload = updateCustomerMock.mock.calls[0][1] as Record<string, unknown>

    // 关键断言：经理字段是 Integer 外键列，后端 setattr(int 列, "") 会 500；
    // 必须归一为 null，后端据此 setattr(..., None) 置 NULL。
    expect(payload).toHaveProperty('manager_id', null)
    expect(payload).toHaveProperty('sales_manager_id', null)
  })

  it('保留经理时 payload 携带原值', async () => {
    const { vm } = await mountDialog()
    await vm.handleSubmit()

    const payload = updateCustomerMock.mock.calls[0][1] as Record<string, unknown>
    expect(payload).toHaveProperty('manager_id', 5)
    expect(payload).toHaveProperty('sales_manager_id', 7)
  })
})
