import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import RechargeRecordModal from '@/views/billing/components/RechargeRecordModal.vue'
import { getRechargeRecords, getCustomerBalance, revokeRechargeRecord } from '@/api/billing'
import type { RechargeRecord } from '@/api/billing'

vi.mock('@/api/billing', () => ({
  getRechargeRecords: vi.fn(),
  getConsumptionRecords: vi.fn().mockResolvedValue({ code: 0, data: { list: [], total: 0 } }),
  getCustomerBalance: vi.fn(),
  revokeRechargeRecord: vi.fn(),
}))

enableAutoUnmount(afterEach)

/** modal stub 额外渲染 ok 按钮，用于触发 before-ok（Arco 真实弹窗行为） */
const stubs = {
  'a-modal': {
    emits: ['before-ok'],
    template:
      '<div><slot /><button class="modal-ok" @click="$emit(\'before-ok\')">ok</button></div>',
  },
  'a-tabs': { emits: ['change'], template: '<div><slot /></div>' },
  'a-tab-pane': { template: '<div><slot /></div>' },
  'a-table': {
    props: ['columns', 'data'],
    template: '<div><slot name="recharge_action" :record="data[0] || {}" /></div>',
  },
  'a-textarea': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'a-form': { template: '<div><slot /></div>' },
  'a-form-item': { template: '<div><slot /></div>' },
  'a-checkbox': { template: '<label><slot /></label>' },
}

function makeRecord(overrides: Partial<RechargeRecord> = {}): RechargeRecord {
  return {
    id: 12,
    customer_id: 101,
    customer_name: '客户A',
    real_amount: 10000,
    bonus_amount: 2000,
    total_amount: 12000,
    operator_id: 1,
    recharge_date: '2026-11-12',
    crm_payment_id: null,
    created_at: '2026-11-12T10:00:00',
    ...overrides,
  } as RechargeRecord
}

async function mountWith(
  record: RechargeRecord,
  props: { can?: (p: string) => boolean; isSuperAdmin?: boolean } = {}
) {
  vi.mocked(getRechargeRecords).mockResolvedValue({
    code: 0,
    data: { list: [record], total: 1, page: 1, page_size: 10 },
  } as never)
  vi.mocked(getCustomerBalance).mockResolvedValue({
    code: 0,
    data: { real_amount: 10000, bonus_amount: 2000, total_amount: 12000 },
  } as never)
  const wrapper = mount(RechargeRecordModal, {
    props: {
      visible: false,
      customerId: 101,
      can: props.can ?? (() => true),
      isSuperAdmin: props.isSuperAdmin ?? false,
    },
    global: { stubs },
  })
  // 打开弹窗才会加载记录（watch 非 immediate）
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

describe('RechargeRecordModal 充值记录撤销', () => {
  beforeEach(() => {
    vi.mocked(revokeRechargeRecord).mockReset()
    vi.mocked(getRechargeRecords).mockClear()
    vi.mocked(getCustomerBalance).mockClear()
  })

  it('手动/导入来源且有权限时显示撤销按钮', async () => {
    const wrapper = await mountWith(makeRecord())
    expect(wrapper.find('.btn-revoke').exists()).toBe(true)
  })

  it('CRM 来源充值不提供撤销入口', async () => {
    const wrapper = await mountWith(makeRecord({ crm_payment_id: 6 }))
    expect(wrapper.find('.btn-revoke').exists()).toBe(false)
  })

  it('无 billing:recharge_revoke 权限时不显示撤销按钮', async () => {
    const wrapper = await mountWith(makeRecord(), { can: (p) => p !== 'billing:recharge_revoke' })
    expect(wrapper.find('.btn-revoke').exists()).toBe(false)
  })

  it('原因必填：未填写时不调用撤销接口', async () => {
    const wrapper = await mountWith(makeRecord())
    await wrapper.find('.btn-revoke').trigger('click')
    await flushPromises()

    const okButtons = wrapper.findAll('.modal-ok')
    await okButtons[okButtons.length - 1].trigger('click')
    await flushPromises()

    expect(revokeRechargeRecord).not.toHaveBeenCalled()
    expect(wrapper.emitted('revoked')).toBeFalsy()
  })

  it('提交撤销：带上原因、刷新列表并通知父页面刷新余额', async () => {
    vi.mocked(revokeRechargeRecord).mockResolvedValue({
      code: 0,
      message: '已撤销充值记录',
      data: { needs_manual_reconciliation: false },
    } as never)

    const wrapper = await mountWith(makeRecord())
    await wrapper.find('.btn-revoke').trigger('click')
    await flushPromises()

    await wrapper.find('textarea').setValue('充错客户')
    const okButtons = wrapper.findAll('.modal-ok')
    await okButtons[okButtons.length - 1].trigger('click')
    await flushPromises()

    expect(revokeRechargeRecord).toHaveBeenCalledWith(12, {
      reason: '充错客户',
      force: false,
    })
    expect(wrapper.emitted('revoked')).toEqual([[101]])
    // 撤销后重新拉取记录列表
    expect(vi.mocked(getRechargeRecords)).toHaveBeenCalledTimes(2)
  })
})
