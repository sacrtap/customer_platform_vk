<template>
  <div class="progress-bar">
    <div
      class="progress-fill"
      :style="{
        width: `${Math.min(100, Math.max(0, value))}%`,
        background: color,
      }"
    />
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    value: number
    color?: string
  }>(),
  {
    color: 'var(--primary)',
  }
)
</script>

<style scoped>
.progress-bar {
  width: 100%;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}
</style>
