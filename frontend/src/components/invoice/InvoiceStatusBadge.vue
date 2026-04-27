<template>
  <a-tag :color="statusConfig.color" size="small">
    {{ statusConfig.text }}
  </a-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  status: string;
}>();

const statusMap: Record<string, { text: string; color: string }> = {
  draft: { text: '草稿', color: 'gray' },
  pending_customer: { text: '待客户确认', color: 'orange' },
  customer_confirmed: { text: '客户已确认', color: 'blue' },
  paid: { text: '已付款', color: 'green' },
  completed: { text: '已完成', color: 'arcoblue' },
  cancelled: { text: '已取消', color: 'red' },
};

const statusConfig = computed(() => {
  return statusMap[props.status] || { text: props.status, color: 'gray' };
});
</script>
