<template>
  <button
    class="header-action"
    :aria-label="label"
    :title="label"
    @click="$emit('click')"
  >
    <slot />
    <span v-if="badge" class="action-badge">{{ badge }}</span>
    <span class="tooltip">{{ label }}</span>
  </button>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  badge?: string | number
}>()

defineEmits<{
  click: []
}>()
</script>

<style scoped>
.header-action {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--neutral-6);
  cursor: pointer;
  transition: background-color var(--transition-fast), color var(--transition-fast);
  position: relative;
  border: none;
  background: transparent;
}

.header-action:hover {
  background: var(--neutral-1);
  color: var(--neutral-9);
}

.header-action svg {
  width: 20px;
  height: 20px;
}

.action-badge {
  position: absolute;
  top: 8px;
  right: 10px;
  min-width: 8px;
  height: 8px;
  background: var(--danger-5);
  border-radius: 50%;
  border: 2px solid white;
  font-size: 0;
}

.tooltip {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  padding: 6px 12px;
  background: var(--neutral-10);
  color: white;
  font-size: 12px;
  font-weight: 500;
  border-radius: 8px;
  white-space: nowrap;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-4px);
  transition: opacity var(--transition-fast), transform var(--transition-fast), visibility var(--transition-fast);
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.tooltip::before {
  content: '';
  position: absolute;
  top: -4px;
  right: 12px;
  width: 8px;
  height: 8px;
  background: var(--neutral-10);
  transform: rotate(45deg);
}

.header-action:hover .tooltip {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}
</style>
