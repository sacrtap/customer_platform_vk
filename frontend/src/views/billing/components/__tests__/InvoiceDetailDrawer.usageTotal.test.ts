import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import InvoiceDetailDrawer from '@/views/billing/components/InvoiceDetailDrawer.vue'

vi.mock('@/stores/user', () => ({
  useUserStore: vi.fn(() => ({ hasPermission: () => true })),
}))

const baseInvoice = {
  id: 1,
  invoice_no: 'INV-TEST',
  status: 'completed',
  final_amount: 100,
  customer_id: 1,
  customer_name: '测试客户',
  period_start: '2026-01-01',
  period_end: '2026-01-31',
  total_amount: 100,
  discount_amount: 0,
  is_auto_generated: false,
  created_at: '2026-01-01T00:00:00',
  created_by_name: '系统',
  items: [] as Array<Record<string, unknown>>,
}

function mountDrawer(invoice: Record<string, unknown>) {
  return mount(InvoiceDetailDrawer, {
    props: { visible: true, invoice: invoice as never },
    global: {
      stubs: {
        'a-drawer': { template: '<div><slot /></div>' },
        'a-modal': { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('计费明细节用量总计行', () => {
  it('无明细时不渲染汇总行', () => {
    const w = mountDrawer(baseInvoice)
    expect(w.find('tfoot').exists()).toBe(false)
  })

  it('items 为 undefined 时不渲染汇总行', () => {
    const w = mountDrawer({ ...baseInvoice, items: undefined })
    expect(w.find('tfoot').exists()).toBe(false)
  })

  it('有明细时渲染汇总行，值 = 各明细 order_count 之和', async () => {
    const w = mountDrawer({
      ...baseInvoice,
      items: [
        {
          id: 1,
          pricing_type: 'fixed',
          quantity: 432,
          order_count: 432,
          unit_price: 8,
          subtotal: 3456,
        },
        {
          id: 2,
          pricing_type: 'fixed',
          quantity: 15,
          order_count: 15,
          unit_price: 8,
          subtotal: 120,
        },
      ],
    })
    await nextTick()
    const foot = w.find('tfoot')
    expect(foot.exists()).toBe(true)
    expect(foot.text()).toContain('用量总计')
    expect(foot.text()).toContain('447')
  })

  it('小数量纲保留小数（formatItemNumber 口径）', async () => {
    const w = mountDrawer({
      ...baseInvoice,
      items: [
        {
          id: 1,
          pricing_type: 'fixed',
          quantity: 1.5,
          order_count: 1.5,
          unit_price: 8,
          subtotal: 12,
        },
        { id: 2, pricing_type: 'fixed', quantity: 1, order_count: 1, unit_price: 8, subtotal: 8 },
      ],
    })
    await nextTick()
    expect(w.find('tfoot').text()).toContain('2.5')
  })

  it('混合计费类型按单数（order_count）汇总，不含楼层数', async () => {
    const w = mountDrawer({
      ...baseInvoice,
      items: [
        // fixed 多层递增：100 层 / 80 单
        {
          id: 1,
          pricing_type: 'fixed',
          multi_floor_pricing_type: 'incremental',
          quantity: 100,
          order_count: 80,
          unit_price: 8,
          subtotal: 800,
        },
        // tiered：200 层 / 150 单
        {
          id: 2,
          pricing_type: 'tiered',
          quantity: 200,
          order_count: 150,
          unit_price: 9,
          subtotal: 1350,
        },
        // package-unlimited：50 层 / 30 单
        {
          id: 3,
          pricing_type: 'package',
          package_type: 'unlimited',
          quantity: 50,
          order_count: 30,
          unit_price: 10,
          subtotal: 1000,
        },
      ],
    })
    await nextTick()
    const text = w.find('tfoot').text()
    expect(text).toContain('260') // 80 + 150 + 30，单数
    expect(text).not.toContain('350') // 100 + 200 + 50，楼层数和
  })

  it('order_count 缺失时回退 quantity（防御历史数据）', async () => {
    const w = mountDrawer({
      ...baseInvoice,
      items: [
        { id: 1, pricing_type: 'fixed', quantity: 100, unit_price: 8, subtotal: 800 },
        { id: 2, pricing_type: 'fixed', quantity: 50, unit_price: 8, subtotal: 400 },
      ],
    })
    await nextTick()
    expect(w.find('tfoot').text()).toContain('150')
  })
})
