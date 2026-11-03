import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, enableAutoUnmount, type VueWrapper } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import InvoiceDetailDrawer from '@/views/billing/components/InvoiceDetailDrawer.vue'

// 挂载的 Arco 组件（Timeline 等）在测试环境销毁后可能残留 requestAnimationFrame，
// 触发 jsdom 未处理异常；enableAutoUnmount 保证每个用例后自动卸载
enableAutoUnmount(afterEach)

// jsdom 不实现 window.matchMedia，Arco 响应式组件（内部 responsive-observe）挂载时需要
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

const permissionState = vi.hoisted(() => ({ allowEdit: true }))
vi.mock('@/stores/user', () => ({
  useUserStore: vi.fn(() => ({
    hasPermission: (p: string) => (p === 'billing:edit' ? permissionState.allowEdit : true),
  })),
}))

const baseInvoice = {
  id: 1,
  invoice_no: 'INV-TEST',
  status: 'draft',
  final_amount: 900,
  customer_id: 1,
  customer_name: '测试客户',
  period_start: '2026-01-01',
  period_end: '2026-01-31',
  total_amount: 1000,
  discount_amount: 100,
  discount_reason: '大客户优惠',
  discount_approver_name: '李四',
  discount_approved_at: '2026-11-03T12:00:00',
  discount_approval_comment: '同意减免',
  is_auto_generated: false,
  created_at: '2026-01-01T00:00:00',
  created_by_name: '系统',
  items: [] as Array<Record<string, unknown>>,
  discount_history: [
    {
      id: 1,
      discount_amount: 100,
      discount_reason: '大客户优惠',
      applied_at: '2026-11-03T10:00:00',
      applied_by_name: '张三',
    },
  ],
}

function mountDrawer(invoice: Record<string, unknown>) {
  return mount(InvoiceDetailDrawer, {
    props: { visible: true, invoice: invoice as never },
    global: {
      plugins: [ArcoVue],
      stubs: {
        'a-drawer': { template: '<div><slot /></div>' },
        'a-modal': { template: '<div><slot /></div>' },
      },
    },
  })
}

function hasDiscountButton(wrapper: VueWrapper): boolean {
  return wrapper.findAll('button').some((b) => b.text().includes('减免'))
}

describe('结算单详情 - 减免展示区（与 VR 结算单详情统一）', () => {
  it('discount_history 非空时渲染「减免修改历史」表格行', () => {
    const w = mountDrawer(baseInvoice)
    expect(w.text()).toContain('减免修改历史')
    // 表格行含原因/操作人；正数减免渲染 - 前缀
    expect(w.text()).toContain('大客户优惠')
    expect(w.text()).toContain('张三')
    expect(w.text()).toContain('-¥100.00')
  })

  it('discount_history 为 [] / undefined 时不渲染该 section', () => {
    expect(mountDrawer({ ...baseInvoice, discount_history: [] }).text()).not.toContain(
      '减免修改历史'
    )
    expect(mountDrawer({ ...baseInvoice, discount_history: undefined }).text()).not.toContain(
      '减免修改历史'
    )
  })

  it('有减免时渲染减免审批人/审批时间/审批意见三项', () => {
    const w = mountDrawer(baseInvoice)
    expect(w.text()).toContain('减免审批人')
    expect(w.text()).toContain('李四')
    expect(w.text()).toContain('减免审批时间')
    expect(w.text()).toContain('审批意见')
    expect(w.text()).toContain('同意减免')
  })

  it('discount_approval_comment 为空时不渲染「审批意见」项', () => {
    const w = mountDrawer({ ...baseInvoice, discount_approval_comment: null })
    expect(w.text()).toContain('减免审批人')
    expect(w.text()).not.toContain('审批意见')
  })

  it('回归防护：pending_customer 不渲染修改减免按钮；draft 渲染', () => {
    expect(hasDiscountButton(mountDrawer({ ...baseInvoice, status: 'pending_customer' }))).toBe(
      false
    )
    expect(hasDiscountButton(mountDrawer({ ...baseInvoice, status: 'draft' }))).toBe(true)
  })

  it('无 billing:edit 权限时不渲染修改减免按钮', () => {
    permissionState.allowEdit = false
    try {
      expect(hasDiscountButton(mountDrawer(baseInvoice))).toBe(false)
    } finally {
      permissionState.allowEdit = true
    }
  })
})
