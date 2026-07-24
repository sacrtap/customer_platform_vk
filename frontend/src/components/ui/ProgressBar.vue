<template>
  <div class="progress-bar">
    <div
      class="progress-fill"
      :style="{
        width: `${Math.min(100, Math.max(0, value))}%`,
        background: color || 'linear-gradient(90deg, #2563eb, #06b6d4)',
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
    color: '',
  }
)
</script>

<style scoped>
.progress-bar {
  width: 100%;
  height: 8px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.3s ease;
}
</style>
