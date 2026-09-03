<template>
  <a-timeline>
    <a-timeline-item v-for="(event, index) in timelineEvents" :key="index" :color="event.dotColor">
      <div :class="['timeline-content', event.textClass]">
        <strong>{{ event.label }}</strong>
        <p v-if="event.operator" class="timeline-operator">操作人：{{ event.operator }}</p>
        <p v-if="event.time" class="timeline-time">{{ event.time }}</p>
        <p v-if="event.detailParts" class="timeline-detail">
          <span v-for="(part, i) in event.detailParts" :key="i">
            <template v-if="part.type === 'link'">
              {{ part.prefix
              }}<a :href="part.url" target="_blank" download class="timeline-attachment-link">{{
                part.label
              }}</a>
            </template>
            <template v-else>
              {{ part.text }}
            </template>
            <span v-if="i < event.detailParts.length - 1"> | </span>
          </span>
        </p>
      </div>
    </a-timeline-item>
  </a-timeline>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { toDate } from '@/utils/formatters'
import type { DiscountHistory } from '@/api/billing'

type DetailPart = {
  type: 'text' | 'link'
  text?: string
  prefix?: string
  label?: string
  url?: string
}

const props = defineProps<{
  invoice: {
    status: string
    created_at: string
    created_by_name?: string | null
    discount_amount?: number
    discount_reason?: string
    discount_attachment?: string
    discount_applied_at?: string
    discount_history?: DiscountHistory[]
    approved_at?: string
    approver_name?: string | null
    ops_confirmed_at?: string
    ops_confirmed_name?: string | null
    sales_confirmed_at?: string
    sales_confirmed_name?: string | null
    customer_confirmed_at?: string
    customer_confirmed_name?: string | null
    paid_at?: string
    completed_at?: string
    completed_name?: string | null
    cancelled_at?: string
    cancelled_name?: string | null
    payment_proof?: string
  }
}>()

const timelineEvents = computed(() => {
  const status = props.invoice.status
  const isCancelled = status === 'cancelled'

  // 定义流程节点（不含减免节点，减免节点单独处理）
  type TimeField =
    | 'created_at'
    | 'approved_at'
    | 'ops_confirmed_at'
    | 'sales_confirmed_at'
    | 'customer_confirmed_at'
    | 'paid_at'
    | 'completed_at'
  type OperatorField =
    | 'created_by_name'
    | 'approver_name'
    | 'ops_confirmed_name'
    | 'sales_confirmed_name'
    | 'customer_confirmed_name'
    | 'completed_name'
    | null

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
      field: 'approved_at',
      label: '提交结算单',
      statusKey: 'pending_ops',
      operatorField: 'approver_name',
    },
    {
      field: 'ops_confirmed_at',
      label: '运营经理确认',
      statusKey: 'pending_sales',
      operatorField: 'ops_confirmed_name',
    },
    {
      field: 'sales_confirmed_at',
      label: '销售经理确认',
      statusKey: 'pending_customer',
      operatorField: 'sales_confirmed_name',
    },
    {
      field: 'customer_confirmed_at',
      label: '客户确认',
      statusKey: 'customer_confirmed',
      operatorField: 'customer_confirmed_name',
    },
    {
      field: 'paid_at',
      label: '确认付款',
      statusKey: 'paid',
      detailParts: () => {
        const proof = props.invoice.payment_proof
        if (!proof) return undefined
        return [{ type: 'text', text: `凭证：${proof}` }]
      },
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

  // 构建减免历史事件（按时间正序，即最早修改在最前）
  const discountHistories = props.invoice.discount_history || []
  // 后端返回的是倒序（最新在前），反转后正序展示
  const sortedHistories = [...discountHistories].reverse()

  const discountEvents = sortedHistories.map((dh, idx) => {
    const parts: DetailPart[] = []
    parts.push({ type: 'text', text: `减免金额：¥${dh.discount_amount || 0}` })
    if (dh.discount_reason) parts.push({ type: 'text', text: `减免说明：${dh.discount_reason}` })
    if (dh.discount_attachment) {
      const fileName = dh.discount_attachment.split('/').pop() || dh.discount_attachment
      parts.push({ type: 'link', prefix: '附件：', label: fileName, url: dh.discount_attachment })
    }

    // 减免节点的颜色：已完成=绿色
    let dotColor = 'green'
    let textClass = 'completed-event'

    return {
      label: `修改减免${discountHistories.length > 1 ? `（第 ${idx + 1} 次）` : ''}`,
      time: dh.applied_at ? formatDate(dh.applied_at) : undefined,
      detailParts: parts,
      operator: dh.applied_by_name || undefined,
      dotColor,
      textClass,
    }
  })

  // 添加创建结算单节点
  const createNode = allNodes[0]
  const createTime = props.invoice[createNode.field] as string | undefined
  if (createTime) {
    events.push({
      label: createNode.label,
      time: formatDate(createTime),
      operator: createNode.operatorField
        ? (props.invoice[createNode.operatorField] as string | null | undefined) || undefined
        : undefined,
      dotColor: 'green',
      textClass: 'completed-event',
    })
  }

  // 如果有减免历史，在创建后插入所有减免历史记录
  events.push(...discountEvents)

  // 添加剩余流程节点（跳过已处理的 created_at）
  const remainingNodes = allNodes.slice(1)

  // 计算当前流程状态对应的节点索引（在 remainingNodes 中的位置）
  let currentRemIndex = -1
  const allCompleted = status === 'completed'
  if (!isCancelled) {
    currentRemIndex = remainingNodes.findIndex((node) => node.statusKey === status)
  }

  remainingNodes.forEach((node, index) => {
    const timeValue = props.invoice[node.field] as string | undefined
    if (!timeValue) return // 只显示已发生的节点

    const isCompleted = timeValue && index !== currentRemIndex
    const isCurrent = !isCancelled && index === currentRemIndex && !allCompleted

    let dotColor: string
    let textClass: string

    if (isCurrent) {
      dotColor = 'blue'
      textClass = 'current-event'
    } else if (isCompleted) {
      dotColor = 'green'
      textClass = 'completed-event'
    } else {
      dotColor = 'gray'
      textClass = 'pending-event'
    }

    events.push({
      label: node.label,
      time: formatDate(timeValue),
      detailParts: node.detailParts ? node.detailParts() : undefined,
      operator: node.operatorField
        ? (props.invoice[node.operatorField] as string | null | undefined) || undefined
        : undefined,
      dotColor,
      textClass,
    })
  })

  // 如果是取消状态，添加取消节点
  if (isCancelled) {
    events.push({
      label: '取消结算单',
      time: props.invoice.cancelled_at ? formatDate(props.invoice.cancelled_at) : undefined,
      operator: (props.invoice.cancelled_name as string | null | undefined) || undefined,
      dotColor: 'red',
      textClass: 'cancelled-event',
    })
  }

  return events
})

/**
 * 将时间字符串按当前时区进行本地化显示。
 * 使用 toDate() 处理时区（见 formatters.ts）。
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

<style scoped>
.timeline-content {
  line-height: 1.6;
}

/* 当前节点：蓝色加粗 */
.current-event {
  color: var(--primary);
  font-weight: 600;
}

/* 已完成节点：绿色 */
.completed-event {
  color: var(--green);
}

/* 未到达节点：灰色 */
.pending-event {
  color: var(--muted);
}

/* 取消节点：红色 */
.cancelled-event {
  color: var(--red);
  font-weight: 600;
}

.timeline-time {
  font-size: 12px;
  color: var(--muted);
  margin: 4px 0 0 0;
}

.timeline-operator {
  font-size: 12px;
  color: var(--ink);
  margin: 2px 0 0 0;
  font-weight: 500;
}

.timeline-detail {
  font-size: 12px;
  color: var(--muted);
  margin: 4px 0 0 0;
}

.timeline-attachment-link {
  color: var(--primary);
  text-decoration: underline;
  cursor: pointer;
}

.timeline-attachment-link:hover {
  opacity: 0.8;
}
</style>
