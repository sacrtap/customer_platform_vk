import { describe, it, expect, afterEach } from 'vitest'
import { mount, enableAutoUnmount, type VueWrapper } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import VrSettlementTimeline from '@/components/vr/VrSettlementTimeline.vue'
import { expectCompletedTerminalTimeline } from '@/components/common/__tests__/timelineAssertions'
import type { VrSettlement } from '@/api/vrSettlement'

// 避免挂载的 Arco 组件（Timeline 等）在测试环境销毁后残留 requestAnimationFrame，
// 触发 jsdom「Cannot read properties of null (reading '_location')」未处理异常
enableAutoUnmount(afterEach)

/** 构造 VR 结算单（默认 draft 空流程，按用例覆盖字段） */
function makeSettlement(overrides: Partial<VrSettlement> = {}): VrSettlement {
  return {
    id: 1,
    settlement_no: 'VR-20261103-101-ABCD',
    customer_id: 101,
    period_start: '2026-11-01T00:00:00',
    period_end: '2026-11-30T23:59:59',
    total_amount: 1000,
    final_amount: 1000,
    status: 'draft',
    detail_file_path: null,
    detail_file_name: null,
    created_at: '2026-11-03T10:00:00',
    created_by_name: '张三',
    ...overrides,
  }
}

function mountTimeline(settlement: VrSettlement): VueWrapper {
  return mount(VrSettlementTimeline, {
    props: { settlement },
    global: { plugins: [ArcoVue] },
  })
}

/** 时间线节点文本（label + operator/time/detail 拼成的纯文本，每节点一条） */
function nodeTexts(wrapper: VueWrapper): string[] {
  return wrapper.findAll('.timeline-content').map((n) => n.text())
}

/** 只取节点 label（文本首个「操作人」前的部分） */
function nodeLabels(wrapper: VueWrapper): string[] {
  return nodeTexts(wrapper).map((t) => t.split('操作人')[0].trim())
}

describe('VrSettlementTimeline 操作记录时间线', () => {
  it('draft 仅显示创建节点（无后续节点）', () => {
    const wrapper = mountTimeline(makeSettlement())

    const texts = nodeTexts(wrapper)
    expect(texts).toHaveLength(1)
    expect(texts[0]).toContain('创建结算单')
    expect(texts[0]).toContain('张三')
  })

  it('已完成流程：全部节点 completed 绿色，无 current 高亮', () => {
    const wrapper = mountTimeline(
      makeSettlement({
        status: 'completed',
        cs_supervisor_confirmed_at: '2026-11-03T11:00:00',
        cs_supervisor_confirmed_name: '李四',
        sales_confirmed_at: '2026-11-03T12:00:00',
        sales_confirmed_name: '王五',
        sales_supervisor_confirmed_at: '2026-11-03T13:00:00',
        sales_supervisor_confirmed_name: '赵六',
        customer_confirmed_at: '2026-11-03T14:00:00',
        customer_confirmed_name: '客户经理',
        completed_at: '2026-11-03T15:00:00',
        completed_name: '系统',
      })
    )

    const texts = nodeTexts(wrapper)
    expect(nodeLabels(wrapper)).toEqual([
      '创建结算单',
      '客服主管审批',
      '销售审批',
      '销售主管审批',
      '客户确认',
      '完成结算',
    ])
    expectCompletedTerminalTimeline(wrapper, 6)
    expect(texts[1]).toContain('李四')
    expect(texts[5]).toContain('系统')
  })

  it('当前所处节点高亮（pending_customer：销售主管已批、客户未确认）', () => {
    const wrapper = mountTimeline(
      makeSettlement({
        status: 'pending_customer',
        cs_supervisor_confirmed_at: '2026-11-03T11:00:00',
        cs_supervisor_confirmed_name: '李四',
        sales_confirmed_at: '2026-11-03T12:00:00',
        sales_confirmed_name: '王五',
        sales_supervisor_confirmed_at: '2026-11-03T13:00:00',
        sales_supervisor_confirmed_name: '赵六',
      })
    )

    // 已发生 4 节点：创建 + 三级审批
    expect(wrapper.findAll('.timeline-content')).toHaveLength(4)
    // 当前节点 = 销售主管审批（pending_customer 是其后置状态），蓝色高亮
    const current = wrapper.findAll('.current-event')
    expect(current).toHaveLength(1)
    expect(current[0].text()).toContain('销售主管审批')
    // 其余 3 个为已完成绿色
    expect(wrapper.findAll('.completed-event')).toHaveLength(3)
  })

  it('取消状态：末位追加红色取消节点', () => {
    const wrapper = mountTimeline(
      makeSettlement({
        status: 'cancelled',
        cancelled_at: '2026-11-03T16:00:00',
        cancelled_name: '张三',
        cs_supervisor_confirmed_at: '2026-11-03T11:00:00',
        cs_supervisor_confirmed_name: '李四',
      })
    )

    const texts = nodeTexts(wrapper)
    expect(texts[texts.length - 1]).toContain('取消结算单')
    const cancelled = wrapper.findAll('.cancelled-event')
    expect(cancelled).toHaveLength(1)
    expect(cancelled[0].text()).toContain('张三')
  })

  it('销售主管节点展示减免审批意见', () => {
    const wrapper = mountTimeline(
      makeSettlement({
        status: 'pending_customer',
        cs_supervisor_confirmed_at: '2026-11-03T11:00:00',
        sales_confirmed_at: '2026-11-03T12:00:00',
        sales_supervisor_confirmed_at: '2026-11-03T13:00:00',
        discount_approval_comment: '同意减免，年末优惠',
      })
    )

    const supervisorNode = wrapper
      .findAll('.timeline-content')
      .find((n) => n.text().includes('销售主管审批'))
    expect(supervisorNode?.text()).toContain('减免审批意见：同意减免，年末优惠')
  })

  it('减免历史插在创建节点之后（正序，多次标注第 N 次）', () => {
    const wrapper = mountTimeline(
      makeSettlement({
        status: 'pending_cs_supervisor',
        discount_history: [
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
        ],
      })
    )

    const texts = nodeTexts(wrapper)
    // 创建 + 两次减免（后端倒序返回，前端反转为正序）
    expect(texts).toHaveLength(3)
    expect(texts[0]).toContain('创建结算单')
    expect(texts[1]).toContain('修改减免（第 1 次）')
    expect(texts[1]).toContain('第一次')
    expect(texts[2]).toContain('修改减免（第 2 次）')
    expect(texts[2]).toContain('第二次')
  })
})
