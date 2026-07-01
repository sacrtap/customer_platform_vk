<template>
  <a-timeline>
    <a-timeline-item
      v-for="(event, index) in timelineEvents"
      :key="index"
      :color="event.dotColor"
    >
      <div :class="['timeline-content', event.textClass]">
        <strong>{{ event.label }}</strong>
        <p v-if="event.time" class="timeline-time">{{ event.time }}</p>
        <p v-if="event.detail" class="timeline-detail">{{ event.detail }}</p>
      </div>
    </a-timeline-item>
  </a-timeline>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  invoice: {
    status: string
    created_at: string
    discount_amount?: number
    discount_reason?: string
    discount_applied_at?: string
    approved_at?: string
    customer_confirmed_at?: string
    paid_at?: string
    completed_at?: string
    cancelled_at?: string
    payment_proof?: string
  }
}>()

const timelineEvents = computed(() => {
  const status = props.invoice.status
  const isCancelled = status === 'cancelled'

  // 定义所有可能的节点（按流程顺序）
  type TimeField = 'created_at' | 'discount_applied_at' | 'approved_at' | 'customer_confirmed_at' | 'paid_at' | 'completed_at'
  const allNodes: Array<{
    field: TimeField
    label: string
    statusKey: string
    condition?: () => boolean
    detail?: () => string | undefined
  }> = [
    {
      field: 'created_at',
      label: '创建结算单',
      statusKey: 'draft',
    },
    {
      field: 'discount_applied_at',
      label: '申请折扣',
      statusKey: 'discount',
      condition: () => (props.invoice.discount_amount || 0) > 0,
      detail: () => {
        const amount = props.invoice.discount_amount
        const reason = props.invoice.discount_reason
        return amount || reason
          ? `折扣金额：¥${amount || 0}${reason ? ` | 折扣原因：${reason}` : ''}`
          : undefined
      },
    },
    {
      field: 'approved_at',
      label: '商务审核通过',
      statusKey: 'pending_customer',
    },
    {
      field: 'customer_confirmed_at',
      label: '客户确认',
      statusKey: 'customer_confirmed',
    },
    {
      field: 'paid_at',
      label: '确认付款',
      statusKey: 'paid',
      detail: () =>
        props.invoice.payment_proof ? `凭证：${props.invoice.payment_proof}` : undefined,
    },
    {
      field: 'completed_at',
      label: '完成结算',
      statusKey: 'completed',
    },
  ]

  // 过滤条件不满足的节点（如折扣金额为 0 时不显示折扣节点）
  const filteredNodes = allNodes.filter((node) => !node.condition || node.condition())

  // 计算当前节点索引
  let currentIndex = -1
  const allCompleted = status === 'completed'
  if (!isCancelled) {
    currentIndex = filteredNodes.findIndex((node) => node.statusKey === status)
  }

  const events: Array<{
    label: string
    time?: string
    detail?: string
    dotColor: string
    textClass: string
  }> = []

  // 添加正常流程节点
  filteredNodes.forEach((node, index) => {
    const timeValue = props.invoice[node.field]
    if (!timeValue) return  // 只显示已发生的节点
    const isCompleted = timeValue && index !== currentIndex
    const isCurrent = !isCancelled && index === currentIndex && !allCompleted

    let dotColor: string
    let textClass: string

    if (isCurrent) {
      // 当前节点：蓝色圆点 + 蓝色加粗文字
      dotColor = 'blue'
      textClass = 'current-event'
    } else if (isCompleted) {
      // 已完成节点：绿色圆点 + 绿色文字
      dotColor = 'green'
      textClass = 'completed-event'
    } else {
      // 未到达节点：灰色圆点 + 灰色文字
      dotColor = 'gray'
      textClass = 'pending-event'
    }

    events.push({
      label: node.label,
      time: timeValue ? formatDate(timeValue) : undefined,
      detail: node.detail ? node.detail() : undefined,
      dotColor,
      textClass,
    })
  })

  // 如果是取消状态，添加取消节点
  if (isCancelled) {
    events.push({
      label: '取消结算单',
      time: props.invoice.cancelled_at ? formatDate(props.invoice.cancelled_at) : undefined,
      dotColor: 'red',
      textClass: 'cancelled-event',
    })
  }

  return events
})

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.timeline-content {
  line-height: 1.6;
}

/* 当前节点：蓝色加粗 */
.current-event {
  color: #1890ff;
  font-weight: 600;
}

/* 已完成节点：绿色 */
.completed-event {
  color: #52c41a;
}

/* 未到达节点：灰色 */
.pending-event {
  color: #999;
}

/* 取消节点：红色 */
.cancelled-event {
  color: #f5222d;
  font-weight: 600;
}

.timeline-time {
  font-size: 12px;
  color: #666;
  margin: 4px 0 0 0;
}

.timeline-detail {
  font-size: 12px;
  color: #888;
  margin: 4px 0 0 0;
}
</style>
