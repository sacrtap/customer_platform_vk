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
  }
)

defineEmits<{ click: [] }>()
</script>

<style scoped>
.kpi-card {
  background: #f8fafc;
  border: 1px solid #edf2f7;
  border-radius: 14px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.18s ease;
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.kpi-card.active {
  border-color: var(--primary);
  box-shadow:
    0 0 0 2px rgba(29, 78, 216, 0.15),
    0 6px 20px rgba(29, 78, 216, 0.12);
}
.kpi-label {
  font-size: 12px;
  color: var(--muted);
}
.kpi-value {
  font-size: 22px;
  font-weight: 850;
  color: var(--ink);
  margin: 4px 0;
}
.kpi-trend {
  font-size: 12px;
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
  color: var(--muted);
}
</style>
