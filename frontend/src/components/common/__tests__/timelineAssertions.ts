import { expect } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'

/**
 * completed 终态时间线的共享断言：invoice / VR 两个 wrapper 的测试共同复用。
 *
 * 覆盖历史缺陷的攻击面——终态末节点曾被两个 wrapper 各自的 `currentRemIndex`
 * 判定误判为「未到达」灰色。状态推导收敛到 `common/timelineStatus.ts` 后，
 * 该断言保证任何接入方在 completed 终态都不会再出现 current / pending 节点。
 */
export function expectCompletedTerminalTimeline(
  wrapper: VueWrapper,
  expectedNodeCount: number
): void {
  const nodes = wrapper.findAll('.timeline-content')
  expect(nodes).toHaveLength(expectedNodeCount)
  expect(wrapper.findAll('.current-event')).toHaveLength(0)
  expect(wrapper.findAll('.pending-event')).toHaveLength(0)
  expect(wrapper.findAll('.completed-event')).toHaveLength(expectedNodeCount)

  // 末节点是终态判定的原始攻击面，必须落在 completed-event 上
  expect(nodes[nodes.length - 1].classes()).toContain('completed-event')
}
