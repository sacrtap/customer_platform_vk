<template>
  <span :class="['risk-tag', levelClass]">
    <span v-if="icon" class="risk-tag__icon" :class="iconClass" />
    <span class="risk-tag__text">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  level?: 'high' | 'medium' | 'low' | 'info'
  icon?: boolean
}>()

const levelClass = computed(() => `risk-tag--${props.level || 'info'}`)
const iconClass = computed(() => `risk-tag__icon--${props.level || 'info'}`)
</script>

<style scoped>
.risk-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  border-radius: 6px;
}
.risk-tag__icon {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.risk-tag__icon--high { background: var(--cop-danger); }
.risk-tag__icon--medium { background: var(--cop-warning); }
.risk-tag__icon--low { background: var(--cop-success); }
.risk-tag__icon--info { background: var(--cop-cyan); }

.risk-tag--high {
  background: rgba(220, 38, 38, 0.12);
  color: var(--cop-danger);
}
.risk-tag--medium {
  background: rgba(217, 119, 6, 0.12);
  color: var(--cop-warning);
}
.risk-tag--low {
  background: rgba(5, 150, 105, 0.12);
  color: var(--cop-success);
}
.risk-tag--info {
  background: rgba(8, 145, 178, 0.12);
  color: var(--cop-cyan);
}
</style>