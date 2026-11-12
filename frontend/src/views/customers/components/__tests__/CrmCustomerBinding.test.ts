import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import { nextTick } from 'vue'
import CrmCustomerBinding from '@/views/customers/components/CrmCustomerBinding.vue'

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

const hasPermissionMock = vi.fn(() => true)
vi.mock('@/stores/user', () => ({
  useUserStore: () => ({ hasPermission: hasPermissionMock }),
}))

const updateBindingMock = vi.fn()
const getCandidatesMock = vi.fn()

vi.mock('@/api/crmRecharge', () => ({
  getCrmCustomerCandidates: (...args: unknown[]) => getCandidatesMock(...args),
  updateCrmCustomerBinding: (...args: unknown[]) => updateBindingMock(...args),
}))

const mountBinding = (props: Record<string, unknown>) =>
  mount(CrmCustomerBinding, {
    props: {
      customerId: 7,
      crmCustomerId: null,
      crmCustomerName: null,
      crmCustomerExternalId: null,
      ...props,
    },
    global: { plugins: [ArcoVue] },
  })

describe('CrmCustomerBinding', () => {
  beforeEach(() => {
    hasPermissionMock.mockReturnValue(true)
    getCandidatesMock.mockResolvedValue({
      data: {
        list: [
          {
            id: 3,
            external_id: 900001,
            name: '验收宜家家居',
            owner_name: '负责人',
            score: 0.86,
            bound_to_current: false,
            unavailable: false,
          },
        ],
        total: 1,
        page: 1,
        page_size: 10,
        directory_updated_at: null,
        directory_synced: true,
      },
    })
    updateBindingMock.mockResolvedValue({
      data: { crm_customer_id: null, crm_customer_external_id: null, crm_customer_name: null },
    })
  })

  it('已绑定时展示客户名与 CRM ID', () => {
    const wrapper = mountBinding({
      crmCustomerId: 3,
      crmCustomerName: '验收宜家家居',
      crmCustomerExternalId: 900001,
    })
    const text = wrapper.text()
    expect(text).toContain('验收宜家家居')
    expect(text).toContain('900001')
    expect(text).toContain('解绑')
  })

  it('未绑定时提供查找入口', () => {
    const wrapper = mountBinding({})
    expect(wrapper.text()).toContain('未绑定 CRM 客户')
    expect(wrapper.findAll('button').some((b) => b.text().includes('查找CRM客户'))).toBe(true)
  })

  it('无绑定权限时禁用查找并提示所需权限', () => {
    hasPermissionMock.mockReturnValue(false)
    const wrapper = mountBinding({})
    const picker = wrapper.findAll('button').find((b) => b.text().includes('查找CRM客户'))
    expect(picker?.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('绑定CRM客户')
  })

  it('解绑后 emit updated 结果', async () => {
    const wrapper = mountBinding({
      crmCustomerId: 3,
      crmCustomerName: '验收宜家家居',
      crmCustomerExternalId: 900001,
    })
    const unbind = wrapper.findAll('button').find((b) => b.text().trim() === '解绑')
    await unbind!.trigger('click')
    await flushPromises()
    await nextTick()
    expect(updateBindingMock).toHaveBeenCalledWith(7, null)
    expect(wrapper.emitted('updated')?.[0]?.[0]).toEqual({
      crm_customer_id: null,
      crm_customer_external_id: null,
      crm_customer_name: null,
    })
  })

  it('查找弹窗加载候选并展示匹配度', async () => {
    const wrapper = mountBinding({})
    const picker = wrapper.findAll('button').find((b) => b.text().includes('查找CRM客户'))
    await picker!.trigger('click')
    await flushPromises()
    await nextTick()
    expect(getCandidatesMock).toHaveBeenCalled()
    expect(document.body.textContent).toContain('验收宜家家居')
    expect(document.body.textContent).toContain('86%')
  })
})
