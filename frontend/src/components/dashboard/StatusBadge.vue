<template>
  <span :class="['status-badge', typeClass, sizeClass]">
    <span v-if="dot" class="status-badge__dot" :class="dotClass" />
    <span class="status-badge__text">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  type?: 'success' | 'warning' | 'danger' | 'info' | 'default'
  size?: 'sm' | 'md' | 'lg'
  dot?: boolean
}>()

const typeClass = computed(() => `status-badge--${props.type || 'default'}`)
const sizeClass = computed(() => `status-badge--${props.size || 'md'}`)
const dotClass = computed(() => `status-badge__dot--${props.type || 'default'}`)
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  border-radius: 9999px;
}
.status-badge--sm {
  padding: 2px 8px;
  font-size: 11px;
}
.status-badge--md {
  padding: 3px 10px;
  font-size: 12px;
}
.status-badge--lg {
  padding: 4px 12px;
  font-size: 13px;
}

.status-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-badge__dot--success { background: var(--cop-success); }
.status-badge__dot--warning { background: var(--cop-warning); }
.status-badge__dot--danger { background: var(--cop-danger); }
.status-badge__dot--info { background: var(--cop-cyan); }
.status-badge__dot--default { background: var(--cop-muted); }

.status-badge--default {
  background: var(--cop-bg);
  color: var(--cop-muted);
}
.status-badge--success {
  background: rgba(5, 150, 105, 0.1);
  color: var(--cop-success);
}
.status-badge--warning {
  background: rgba(217, 119, 6, 0.1);
  color: var(--cop-warning);
}
.status-badge--danger {
  background: rgba(220, 38, 38, 0.1);
  color: var(--cop-danger);
}
.status-badge--info {
  background: rgba(8, 145, 178, 0.1);
  color: var(--cop-cyan);
}
</style>