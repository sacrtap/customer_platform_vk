import { describe, it, expect, afterEach } from 'vitest'
import { mount, enableAutoUnmount, type VueWrapper } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import InvoiceTimeline from '@/components/invoice/InvoiceTimeline.vue'
import { expectCompletedTerminalTimeline } from '@/components/common/__tests__/timelineAssertions'
import type { DiscountHistory } from '@/api/billing'

// 避免挂载的 Arco 组件（Timeline 等）在测试环境销毁后残留 requestAnimationFrame，
// 触发 jsdom「Cannot read properties of null (reading '_location')」未处理异常
enableAutoUnmount(afterEach)

/**
 * 渲染层抽取回归守护：InvoiceTimeline 的节点推导 computed 在 2026-11-03
 * 重构中零改动（仅模板换为 StatusTimeline），本测试锁定其输出契约。
 */
function makeInvoice(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    status: 'draft',
    created_at: '2026-11-03T10:00:00',
    created_by_name: '张三',
    ...overrides,
  }
}

function mountTimeline(invoice: Record<string, unknown>): VueWrapper {
  return mount(InvoiceTimeline, {
    props: { invoice: invoice as never },
    global: { plugins: [ArcoVue] },
  })
}

function nodeLabels(wrapper: VueWrapper): string[] {
  return wrapper.findAll('.timeline-content').map((n) => n.text().split('操作人')[0].trim())
}

describe('InvoiceTimeline（渲染层抽取回归守护）', () => {
  it('draft 仅显示创建节点', () => {
    const wrapper = mountTimeline(makeInvoice())

    expect(nodeLabels(wrapper)).toEqual(['创建结算单'])
    expect(wrapper.text()).toContain('张三')
  })

  it('完整流程：节点序列与操作人正确', () => {
    const wrapper = mountTimeline(
      makeInvoice({
        status: 'customer_confirmed',
        approved_at: '2026-11-03T11:00:00',
        approver_name: '李四',
        ops_confirmed_at: '2026-11-03T12:00:00',
        ops_confirmed_name: '王五',
        sales_confirmed_at: '2026-11-03T13:00:00',
        sales_confirmed_name: '赵六',
        customer_confirmed_at: '2026-11-03T14:00:00',
        customer_confirmed_name: '客户经理',
      })
    )

    expect(nodeLabels(wrapper)).toEqual([
      '创建结算单',
      '提交结算单',
      '运营经理确认',
      '销售经理确认',
      '客户确认',
    ])
    // 当前节点 = 客户确认（customer_confirmed 状态停在此）
    const current = wrapper.findAll('.current-event')
    expect(current).toHaveLength(1)
    expect(current[0].text()).toContain('客户确认')
  })

  it('completed 终态：全部节点为已完成绿色，无未到达灰节点', () => {
    // 回归守护：修复前末节点「完成结算」被误判为 currentRemIndex 命中而渲染成灰色
    const wrapper = mountTimeline(
      makeInvoice({
        status: 'completed',
        approved_at: '2026-11-03T11:00:00',
        approver_name: '李四',
        ops_confirmed_at: '2026-11-03T12:00:00',
        ops_confirmed_name: '王五',
        sales_confirmed_at: '2026-11-03T13:00:00',
        sales_confirmed_name: '赵六',
        customer_confirmed_at: '2026-11-03T14:00:00',
        customer_confirmed_name: '客户经理',
        completed_at: '2026-11-03T15:00:00',
        completed_name: '系统',
      })
    )

    expect(nodeLabels(wrapper)).toEqual([
      '创建结算单',
      '提交结算单',
      '运营经理确认',
      '销售经理确认',
      '客户确认',
      '完成结算',
    ])
    // 终态无「当前」节点，全部已发生节点均应为绿色（共享断言，与 VR 时间线同源）
    expectCompletedTerminalTimeline(wrapper, 6)
  })

  it('取消状态：末位红色取消节点', () => {
    const wrapper = mountTimeline(
      makeInvoice({
        status: 'cancelled',
        cancelled_at: '2026-11-03T16:00:00',
        cancelled_name: '张三',
      })
    )

    expect(nodeLabels(wrapper)).toEqual(['创建结算单', '取消结算单'])
    expect(wrapper.findAll('.cancelled-event')).toHaveLength(1)
  })

  it('减免历史插在创建之后（正序，多次标注第 N 次）', () => {
    const discountHistory: DiscountHistory[] = [
      {
        id: 2,
        discount_amount: 200,
        discount_reason: '第二次',
        applied_at: '2026-11-03T12:00:00',
        applied_by_name: '王五',
      },
      {
        id: 1,
        discount_amount: 100,
        discount_reason: '第一次',
        applied_at: '2026-11-03T11:00:00',
        applied_by_name: '张三',
      },
    ]

    const wrapper = mountTimeline(makeInvoice({ discount_history: discountHistory }))

    const labels = nodeLabels(wrapper)
    expect(labels).toHaveLength(3)
    expect(labels[0]).toBe('创建结算单')
    expect(labels[1]).toContain('修改减免（第 1 次）')
    expect(labels[2]).toContain('修改减免（第 2 次）')
    expect(wrapper.text()).toContain('第一次')
    expect(wrapper.text()).toContain('第二次')
  })
})
