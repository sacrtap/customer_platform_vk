<template>
  <span :class="['tag', statusConfig.cls]">
    <span class="status-dot"></span>
    {{ statusConfig.text }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { INVOICE_STATUS_MAP, INVOICE_STATUS_CLASS_MAP } from '@/constants/invoiceStatus'

const props = defineProps<{
  status: string
}>()

const statusConfig = computed(() => {
  return {
    text: INVOICE_STATUS_MAP[props.status] || props.status,
    cls: INVOICE_STATUS_CLASS_MAP[props.status] || 'gray',
  }
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
