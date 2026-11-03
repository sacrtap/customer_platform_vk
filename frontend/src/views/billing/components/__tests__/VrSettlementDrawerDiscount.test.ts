import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, enableAutoUnmount, type VueWrapper } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import VrSettlementDetailDrawer from '@/views/billing/components/VrSettlementDetailDrawer.vue'

// 挂载的 Arco 组件（Steps/Timeline 等）在测试环境销毁后可能残留 requestAnimationFrame，
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
    hasPermission: (p: string) => (p === 'vr_settlement:edit' ? permissionState.allowEdit : true),
  })),
}))

const baseSettlement = {
  id: 1,
  settlement_no: 'VR-TEST',
  status: 'pending_sales_supervisor',
  customer_id: 1,
  customer_name: '测试客户',
  period_start: '2026-11-01',
  period_end: '2026-11-30',
  total_amount: 1000,
  discount_amount: 0,
  final_amount: 1000,
  created_at: '2026-11-03T10:00:00',
  detail_file_path: '/uploads/test.xlsx',
  detail_file_name: 'test.xlsx',
  discount_history: [
    {
      id: 1,
      discount_amount: 100,
      discount_reason: '主管审批前补充减免',
      applied_at: '2026-11-03T10:00:00',
      applied_by_name: '张三',
    },
  ],
}

function mountDrawer(settlement: Record<string, unknown>): VueWrapper {
  return mount(VrSettlementDetailDrawer, {
    props: { visible: true, settlement: settlement as never },
    global: {
      plugins: [ArcoVue],
      stubs: {
        'a-drawer': { template: '<div><slot /></div>' },
        'a-modal': { template: '<div><slot /></div>' },
        // 时间线内部依赖由 VrSettlementTimeline 单测覆盖，此处隔离
        VrSettlementTimeline: { template: '<div/>' },
      },
    },
  })
}

function hasDiscountButton(wrapper: VueWrapper): boolean {
  return wrapper.findAll('button').some((b) => b.text().includes('减免'))
}

describe('VR 结算单详情 - 减免提交窗口', () => {
  it('pending_sales_supervisor（销售主管审批通过前）渲染设置减免按钮', () => {
    expect(hasDiscountButton(mountDrawer(baseSettlement))).toBe(true)
  })

  it('pending_customer（销售主管审批通过后）不渲染减免按钮', () => {
    expect(hasDiscountButton(mountDrawer({ ...baseSettlement, status: 'pending_customer' }))).toBe(
      false
    )
  })

  it('无 vr_settlement:edit 权限时不渲染减免按钮', () => {
    permissionState.allowEdit = false
    try {
      expect(hasDiscountButton(mountDrawer(baseSettlement))).toBe(false)
    } finally {
      permissionState.allowEdit = true
    }
  })

  it('discount_history 非空时渲染「减免修改历史」section 与行内容', () => {
    const w = mountDrawer(baseSettlement)
    expect(w.text()).toContain('减免修改历史')
    expect(w.text()).toContain('主管审批前补充减免')
    expect(w.text()).toContain('张三')
    expect(w.text()).toContain('-¥100.00')
  })

  it('discount_history 为空时不渲染「减免修改历史」section', () => {
    expect(mountDrawer({ ...baseSettlement, discount_history: [] }).text()).not.toContain(
      '减免修改历史'
    )
  })
})
