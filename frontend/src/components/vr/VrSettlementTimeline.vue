<template>
  <StatusTimeline :events="timelineEvents" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { toDate } from '@/utils/formatters'
import StatusTimeline from '@/components/common/StatusTimeline.vue'
import type { TimelineDetailPart as DetailPart } from '@/components/common/timelineStatus'
import { resolveTimelineNodeStyle, TIMELINE_STYLES } from '@/components/common/timelineStatus'
import type { VrSettlement } from '@/api/vrSettlement'

const props = defineProps<{
  settlement: VrSettlement
}>()

const timelineEvents = computed(() => {
  const status = props.settlement.status
  const isCancelled = status === 'cancelled'

  // VR 流程节点（状态机：draft → pending_cs_supervisor → pending_sales
  //   → pending_sales_supervisor → pending_customer → customer_confirmed → completed）
  // statusKey = 该节点完成后进入的状态；created_at 无「前一状态」，占位 draft
  type TimeField =
    | 'created_at'
    | 'cs_supervisor_confirmed_at'
    | 'sales_confirmed_at'
    | 'sales_supervisor_confirmed_at'
    | 'customer_confirmed_at'
    | 'completed_at'
  type OperatorField =
    | 'created_by_name'
    | 'cs_supervisor_confirmed_name'
    | 'sales_confirmed_name'
    | 'sales_supervisor_confirmed_name'
    | 'customer_confirmed_name'
    | 'completed_name'

  const allNodes: Array<{
    field: TimeField
    label: string
    statusKey: string
    operatorField?: OperatorField
    detailParts?: () => DetailPart[] | undefined
  }> = [
    {
      field: 'created_at',
      label: '创建结算单',
      statusKey: 'draft',
      operatorField: 'created_by_name',
    },
    {
      field: 'cs_supervisor_confirmed_at',
      label: '客服主管审批',
      statusKey: 'pending_sales',
      operatorField: 'cs_supervisor_confirmed_name',
    },
    {
      field: 'sales_confirmed_at',
      label: '销售审批',
      statusKey: 'pending_sales_supervisor',
      operatorField: 'sales_confirmed_name',
    },
    {
      field: 'sales_supervisor_confirmed_at',
      label: '销售主管审批',
      statusKey: 'pending_customer',
      operatorField: 'sales_supervisor_confirmed_name',
      // 减免审批由销售主管在审批节点一并完成，意见随该节点展示
      detailParts: () =>
        props.settlement.discount_approval_comment
          ? [
              {
                type: 'text',
                text: `减免审批意见：${props.settlement.discount_approval_comment}`,
              },
            ]
          : undefined,
    },
    {
      field: 'customer_confirmed_at',
      label: '客户确认',
      statusKey: 'customer_confirmed',
      operatorField: 'customer_confirmed_name',
    },
    {
      field: 'completed_at',
      label: '完成结算',
      statusKey: 'completed',
      operatorField: 'completed_name',
    },
  ]

  const events: Array<{
    label: string
    time?: string
    detailParts?: DetailPart[]
    operator?: string
    dotColor: string
    textClass: string
  }> = []

  // 构建减免历史事件（按时间正序，最早修改在最前；后端返回倒序需反转）
  const discountHistories = props.settlement.discount_history || []
  const sortedHistories = [...discountHistories].reverse()

  const discountEvents = sortedHistories.map((dh, idx) => {
    const parts: DetailPart[] = []
    parts.push({ type: 'text', text: `减免金额：¥${dh.discount_amount || 0}` })
    if (dh.discount_reason) parts.push({ type: 'text', text: `减免说明：${dh.discount_reason}` })
    if (dh.discount_attachment) {
      const fileName = dh.discount_attachment.split('/').pop() || dh.discount_attachment
      parts.push({ type: 'link', prefix: '附件：', label: fileName, url: dh.discount_attachment })
    }

    return {
      label: `修改减免${discountHistories.length > 1 ? `（第 ${idx + 1} 次）` : ''}`,
      time: dh.applied_at ? formatDate(dh.applied_at) : undefined,
      detailParts: parts,
      operator: dh.applied_by_name || undefined,
      ...TIMELINE_STYLES.completed,
    }
  })

  // 添加创建结算单节点
  const createNode = allNodes[0]
  const createTime = props.settlement[createNode.field] as string | undefined
  if (createTime) {
    events.push({
      label: createNode.label,
      time: formatDate(createTime),
      operator: createNode.operatorField
        ? (props.settlement[createNode.operatorField] as string | null | undefined) || undefined
        : undefined,
      ...TIMELINE_STYLES.completed,
    })
  }

  // 减免历史插在创建之后（与发票详情时间线同规则）
  events.push(...discountEvents)

  // 添加剩余流程节点（跳过已处理的 created_at）
  const remainingNodes = allNodes.slice(1)

  remainingNodes.forEach((node) => {
    const timeValue = props.settlement[node.field] as string | undefined
    if (!timeValue) return // 只显示已发生的节点

    events.push({
      label: node.label,
      time: formatDate(timeValue),
      detailParts: node.detailParts ? node.detailParts() : undefined,
      operator: node.operatorField
        ? (props.settlement[node.operatorField] as string | null | undefined) || undefined
        : undefined,
      // 状态推导（含 completed 终态 / 当前节点）统一由共享层负责
      ...resolveTimelineNodeStyle(node, status, !!timeValue),
    })
  })

  // 取消状态：末位插红色节点
  if (isCancelled) {
    events.push({
      label: '取消结算单',
      time: props.settlement.cancelled_at ? formatDate(props.settlement.cancelled_at) : undefined,
      operator: (props.settlement.cancelled_name as string | null | undefined) || undefined,
      ...TIMELINE_STYLES.cancelled,
    })
  }

  return events
})

/**
 * 将时间字符串按当前时区进行本地化显示。
 * 使用 toDate() 处理时区（见 formatters.ts），与 InvoiceTimeline 同规则。
 */
function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const date = toDate(dateStr)
  if (!date) return ''
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>
