<!-- frontend/src/components/StatCard.vue -->
<template>
  <div class="stat-card" :class="[variant, layout]">
    <div v-if="layout === 'default'" class="stat-header">
      <span class="stat-title">{{ title }}</span>
      <div v-if="icon" class="stat-icon" :class="variant">
        <slot name="icon" />
      </div>
    </div>

    <div v-if="layout === 'compact'" class="stat-header-compact">
      <div v-if="icon" class="stat-icon" :class="variant">
        <slot name="icon" />
      </div>
      <span class="stat-title">{{ title }}</span>
    </div>

    <div class="stat-value" :class="valueClass">{{ value }}</div>

    <div v-if="$slots.subtitle || subtitle" class="stat-subtitle">
      <slot name="subtitle">
        {{ subtitle }}
      </slot>
    </div>

    <div v-if="$slots.extra" class="stat-extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    value: string | number
    subtitle?: string
    variant?: 'primary' | 'success' | 'warning' | 'danger' | 'default'
    layout?: 'default' | 'compact'
    icon?: boolean
    valueClass?: string
  }>(),
  {
    variant: 'default',
    layout: 'default',
    icon: true,
    subtitle: '',
    valueClass: '',
  }
)
</script>

<style scoped>
.stat-card {
  background: white;
  border-radius: var(--radius);
  padding: var(--spacing-xl);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--line);
  transition:
    box-shadow var(--transition-base),
    transform var(--transition-base);
  position: relative;
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #1d4ed8, #2563eb);
}

.stat-card.success::before {
  background: linear-gradient(90deg, #34d399, var(--green));
}

.stat-card.warning::before {
  background: linear-gradient(90deg, #fbbf24, var(--amber));
}

.stat-card.danger::before {
  background: linear-gradient(90deg, #f87171, var(--red));
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.stat-header-compact {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.primary {
  background: #dbeafe;
  color: var(--primary);
}

.stat-icon.success {
  background: #dcfce7;
  color: var(--green);
}

.stat-icon.warning {
  background: #fef3c7;
  color: var(--amber);
}

.stat-icon.danger {
  background: #fee2e2;
  color: var(--red);
}

.stat-icon svg {
  width: 22px;
  height: 22px;
}

.stat-value {
  font-size: 28px;
  font-weight: 850;
  color: var(--ink);
  margin-bottom: 8px;
}

.stat-value.success {
  color: var(--green);
}

.stat-value.warning {
  color: var(--amber);
}

.stat-value.danger {
  color: var(--red);
}

.stat-subtitle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}

.stat-extra {
  font-size: 12px;
  color: var(--muted);
  margin-top: 8px;
}
</style>
