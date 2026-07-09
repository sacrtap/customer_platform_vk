<template>
  <article class="metric-card cop-card">
    <div class="metric-card__label">{{ label }}</div>
    <div class="metric-card__value">{{ value }}</div>
    <div v-if="trend" :class="['metric-card__trend', trendTypeClass]">{{ trend }}</div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value: string | number
  trend?: string
  trendType?: 'up' | 'down' | 'warn' | 'neutral'
}>()

const trendTypeClass = computed(() => `metric-card__trend--${props.trendType || 'neutral'}`)
</script>

<style scoped>
.metric-card {
  padding: 16px;
}
.metric-card__label {
  color: var(--cop-muted);
  font-size: 12px;
}
.metric-card__value {
  margin-top: 5px;
  font-size: 25px;
  font-weight: 850;
}
.metric-card__trend {
  margin-top: 8px;
  font-size: 12px;
}
.metric-card__trend--up {
  color: var(--cop-success);
}
.metric-card__trend--down {
  color: var(--cop-danger);
}
.metric-card__trend--warn {
  color: var(--cop-warning);
}
.metric-card__trend--neutral {
  color: var(--cop-muted);
}
</style>