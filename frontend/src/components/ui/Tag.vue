<template>
  <span class="tag" :class="[variant, size]">
    <slot />
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'blue' | 'green' | 'amber' | 'red' | 'violet' | 'gray'
    size?: 'sm' | 'md'
  }>(),
  {
    variant: 'gray',
    size: 'md',
  }
)
</script>

<style scoped>
.tag {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-weight: 700;
  white-space: nowrap;
}
.tag.sm {
  padding: 2px 6px;
  font-size: 11px;
}
.tag.md {
  padding: 4px 8px;
  font-size: 12px;
}
.tag.blue {
  background: #dbeafe;
  color: #1d4ed8;
}
.tag.green {
  background: #dcfce7;
  color: #047857;
}
.tag.amber {
  background: #fef3c7;
  color: #b45309;
}
.tag.red {
  background: #fee2e2;
  color: #b91c1c;
}
.tag.violet {
  background: #ede9fe;
  color: #6d28d9;
}
.tag.gray {
  background: #f1f5f9;
  color: #475569;
}
</style>
