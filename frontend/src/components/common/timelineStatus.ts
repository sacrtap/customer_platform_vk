export type TimelineDetailPart =
  | { type: 'text'; text: string }
  | { type: 'link'; prefix?: string; label: string; url: string }

/**
 * 流程节点定义：时间字段 + 完成后进入的状态 + 操作人字段 + 附加详情。
 * `statusKey` 在单条时间线内必须唯一——状态推导依赖它定位「当前节点」。
 */
export interface TimelineNodeDefinition {
  field: string
  label: string
  statusKey: string
  operatorField?: string | null
  detailParts?: () => TimelineDetailPart[] | undefined
}

export interface TimelineNodeStyle {
  /** a-timeline-item 的 dot 颜色：blue=当前 / green=已完成 / gray=未到达 / red=取消 */
  dotColor: 'blue' | 'green' | 'gray' | 'red'
  /** 节点文案样式类：current-event / completed-event / pending-event / cancelled-event */
  textClass: 'current-event' | 'completed-event' | 'pending-event' | 'cancelled-event'
}

export const TIMELINE_STYLES = {
  current: { dotColor: 'blue', textClass: 'current-event' },
  completed: { dotColor: 'green', textClass: 'completed-event' },
  pending: { dotColor: 'gray', textClass: 'pending-event' },
  cancelled: { dotColor: 'red', textClass: 'cancelled-event' },
} as const satisfies Record<string, TimelineNodeStyle>

/**
 * 节点状态的**唯一推导处**：发票 / VR 结算单时间线 wrapper 不得各自实现判定。
 *
 * - completed 终态：全部节点都是已完成，不存在 current
 *   （历史缺陷：末节点命中 currentRemIndex 被误判为灰色未到达）
 * - cancelled：流程节点按已完成展示，取消节点由调用方用 `TIMELINE_STYLES.cancelled` 追加
 * - 其余状态：`statusKey` 命中 `status` 的节点为 current，已发生的其他节点为 completed
 * - 无时间戳（尚未发生）的节点为 pending
 */
export function resolveTimelineNodeStyle(
  node: TimelineNodeDefinition,
  status: string,
  hasTime: boolean
): TimelineNodeStyle {
  if (!hasTime) return TIMELINE_STYLES.pending
  if (status === 'completed' || status === 'cancelled') return TIMELINE_STYLES.completed
  return node.statusKey === status ? TIMELINE_STYLES.current : TIMELINE_STYLES.completed
}
