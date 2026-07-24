<template>
  <div class="kpi-card" :class="{ active }" @click="$emit('click')">
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-value">{{ value }}</div>
    <div v-if="trend" class="kpi-trend" :class="trendType">{{ trend }}</div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string | number
    trend?: string
    trendType?: 'up' | 'down' | 'warn' | 'neutral'
    active?: boolean
  }>(),
  {
    trendType: 'neutral',
    active: false,
    trend: '',
  }
)

defineEmits<{ click: [] }>()
</script>

<style scoped>
.kpi-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 16px;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(29, 78, 216, 0.12);
  border-color: #93c5fd;
}
.kpi-card.active {
  border-color: var(--primary);
  box-shadow:
    0 0 0 2px rgba(29, 78, 216, 0.15),
    0 6px 20px rgba(29, 78, 216, 0.12);
}
.kpi-card.active .kpi-value {
  color: var(--primary);
}
.kpi-label {
  font-size: 12px;
  color: var(--muted);
}
.kpi-value {
  font-size: 25px;
  font-weight: 850;
  color: var(--ink);
  margin-top: 5px;
}
.kpi-trend {
  font-size: 12px;
  margin-top: 8px;
}
.kpi-trend.up {
  color: #059669;
}
.kpi-trend.down {
  color: #dc2626;
}
.kpi-trend.warn {
  color: #d97706;
}
.kpi-trend.neutral {
  color: var(--ink);
}
</style>
