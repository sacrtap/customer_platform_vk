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
withDefaults(defineProps<{
  title: string
  value: string | number
  subtitle?: string
  variant?: 'primary' | 'success' | 'warning' | 'danger' | 'default'
  layout?: 'default' | 'compact'
  icon?: boolean
  valueClass?: string
}>(), {
  variant: 'default',
  layout: 'default'
})
</script>

<style scoped>
.stat-card {
  background: white;
  border-radius: var(--radius-lg, 16px);
  padding: var(--spacing-xl, 24px);
  box-shadow: var(--shadow-sm, 0 1px 2px rgba(0, 0, 0, 0.04));
  border: 1px solid var(--neutral-2, #eef0f3);
  transition:
    box-shadow var(--transition-base, 250ms cubic-bezier(0.4, 0, 0.2, 1)),
    transform var(--transition-base, 250ms cubic-bezier(0.4, 0, 0.2, 1));
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
  background: linear-gradient(90deg, var(--primary-5) 0%, var(--primary-6) 100%);
}

.stat-card.success::before {
  background: linear-gradient(90deg, var(--success-5) 0%, var(--success-6) 100%);
}

.stat-card.warning::before {
  background: linear-gradient(90deg, var(--warning-5) 0%, var(--warning-6) 100%);
}

.stat-card.danger::before {
  background: linear-gradient(90deg, var(--danger-5) 0%, var(--danger-6) 100%);
}

.stat-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
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
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-6);
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
  background: var(--primary-1);
  color: var(--primary-6);
}

.stat-icon.success {
  background: var(--success-1);
  color: var(--success-6);
}

.stat-icon.warning {
  background: var(--warning-1);
  color: var(--warning-6);
}

.stat-icon.danger {
  background: var(--danger-1);
  color: var(--danger-6);
}

.stat-icon svg {
  width: 22px;
  height: 22px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--neutral-10);
  margin-bottom: 8px;
}

.stat-value.success {
  color: var(--success-6);
}

.stat-value.warning {
  color: var(--warning-6);
}

.stat-value.danger {
  color: var(--danger-6);
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
  color: var(--neutral-5);
  margin-top: 8px;
}
</style>
