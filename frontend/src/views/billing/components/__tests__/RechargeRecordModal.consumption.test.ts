import { describe, it, expect, afterEach, vi } from 'vitest'
import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import RechargeRecordModal from '@/views/billing/components/RechargeRecordModal.vue'
import type { ConsumptionRecord } from '@/api/billing'
import { getConsumptionRecords } from '@/api/billing'

vi.mock('@/api/billing', () => ({
  getRechargeRecords: vi.fn().mockResolvedValue({ code: 0, data: { list: [], total: 0 } }),
  getConsumptionRecords: vi.fn(),
}))

// 同 BalanceTable：Arco 组件销毁后残留 rAF 会触发 jsdom 未处理异常
enableAutoUnmount(afterEach)

/**
 * stub modal/tabs 规避 teleport 与懒渲染（同 BatchDownloadDetailModal 模式）；
 * table 只透传「关联结算单」slot，用首行数据驱动渲染。
 */
const stubs = {
  'a-modal': { name: 'AModalStub', template: '<div><slot /></div>' },
  'a-tabs': { name: 'ATabsStub', emits: ['change'], template: '<div><slot /></div>' },
  'a-tab-pane': { template: '<div><slot /></div>' },
  'a-table': {
    props: ['columns', 'data'],
    template: '<div><slot name="invoice_no" :record="data[0] || {}" /></div>',
  },
}

/** 构造消耗记录（默认无关联，可按需覆盖为 VR/发票关联） */
function makeRecord(overrides: Partial<ConsumptionRecord> = {}): ConsumptionRecord {
  return {
    id: 1,
    customer_id: 101,
    amount: 500,
    bonus_used: 0,
    real_used: 500,
    balance_after: 500,
    consumed_at: '2026-11-03T10:00:00',
    ...overrides,
  }
}

/** 挂载弹窗、切到消耗记录 tab 并等待列表加载完成 */
async function mountWith(records: ConsumptionRecord[]) {
  vi.mocked(getConsumptionRecords).mockResolvedValue({
    code: 0,
    data: { list: records, total: records.length, page: 1, page_size: 10 },
  } as never)
  const wrapper = mount(RechargeRecordModal, {
    props: { visible: true, customerId: 101 },
    global: { stubs },
  })
  await wrapper.findComponent({ name: 'ATabsStub' }).vm.$emit('change', 'consumption')
  await flushPromises()
  return wrapper
}

describe('RechargeRecordModal 消耗记录「关联结算单」列', () => {
  it('VR 扣款记录显示 vr_settlement_no 并链接 VR 结算单详情', async () => {
    const wrapper = await mountWith([
      makeRecord({ vr_settlement_id: 77, vr_settlement_no: 'VR-20261103-101-ABCD' }),
    ])

    const link = wrapper.find('a.invoice-link')
    expect(link.exists()).toBe(true)
    expect(link.text()).toBe('VR-20261103-101-ABCD')
    expect(link.attributes('href')).toBe('/billing/vr-settlements?highlight=77')
  })

  it('发票扣款记录仍显示 invoice_no 并链接发票详情', async () => {
    const wrapper = await mountWith([
      makeRecord({ invoice_id: 55, invoice_no: 'INV-20261103-101-1234' }),
    ])

    const link = wrapper.find('a.invoice-link')
    expect(link.text()).toBe('INV-20261103-101-1234')
    expect(link.attributes('href')).toBe('/billing/invoices?highlight=55')
  })

  it('无关联记录显示占位符', async () => {
    const wrapper = await mountWith([makeRecord()])

    expect(wrapper.find('a.invoice-link').exists()).toBe(false)
    expect(wrapper.text()).toContain('-')
  })
})
