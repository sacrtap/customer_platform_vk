<template>
  <a-timeline>
    <a-timeline-item
      v-for="event in timelineEvents"
      :key="event.time"
      :time="event.time"
      :color="event.color"
    >
      <div class="timeline-content">
        <strong>{{ event.label }}</strong>
        <p v-if="event.detail" class="timeline-detail">{{ event.detail }}</p>
      </div>
    </a-timeline-item>
  </a-timeline>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  invoice: {
    created_at: string;
    approved_at?: string;
    customer_confirmed_at?: string;
    paid_at?: string;
    completed_at?: string;
    cancelled_at?: string;
    payment_proof?: string;
  };
}>();

const timelineEvents = computed(() => {
  const events: Array<{ time: string; label: string; detail?: string; color?: string }> = [];

  if (props.invoice.created_at) {
    events.push({
      time: formatDate(props.invoice.created_at),
      label: '创建结算单',
    });
  }

  if (props.invoice.approved_at) {
    events.push({
      time: formatDate(props.invoice.approved_at),
      label: '提交结算',
    });
  }

  if (props.invoice.customer_confirmed_at) {
    events.push({
      time: formatDate(props.invoice.customer_confirmed_at),
      label: '客户确认',
    });
  }

  if (props.invoice.paid_at) {
    events.push({
      time: formatDate(props.invoice.paid_at),
      label: '确认付款',
      detail: props.invoice.payment_proof ? `凭证：${props.invoice.payment_proof}` : undefined,
    });
  }

  if (props.invoice.completed_at) {
    events.push({
      time: formatDate(props.invoice.completed_at),
      label: '完成结算',
      color: 'green',
    });
  }

  if (props.invoice.cancelled_at) {
    events.push({
      time: formatDate(props.invoice.cancelled_at),
      label: '取消结算单',
      color: 'red',
    });
  }

  return events;
});

function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
</script>

<style scoped>
.timeline-content {
  padding-left: 8px;
}
.timeline-detail {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-3);
}
</style>
