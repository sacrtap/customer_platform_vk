<template>
  <span :class="['tag', statusConfig.cls]">
    <span class="status-dot"></span>
    {{ statusConfig.text }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: string
}>()

const statusMap: Record<string, { text: string; cls: string }> = {
  draft: { text: '草稿', cls: 'gray' },
  pending_ops: { text: '待运营经理确认', cls: 'amber' },
  pending_sales: { text: '待销售经理确认', cls: 'amber' },
  pending_customer: { text: '待客户确认', cls: 'orange' },
  customer_confirmed: { text: '客户已确认', cls: 'blue' },
  paid: { text: '已付款', cls: 'green' },
  completed: { text: '已完成', cls: 'green' },
  cancelled: { text: '已取消', cls: 'red' },
}

const statusConfig = computed(() => {
  return statusMap[props.status] || { text: props.status, cls: 'gray' }
})
</script>

<style scoped>
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  margin-right: 4px;
}
</style>
