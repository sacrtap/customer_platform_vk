<template>
  <div class="card pad chart-card">
    <div class="section-title">
      <h2>{{ title }}</h2>
      <div v-if="$slots.actions" class="actions">
        <slot name="actions" />
      </div>
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
// 图表卡片组件 — 来源: design.md 4.4
defineProps<{
  title: string
}>()
</script>

<style scoped>
.chart-card {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--line);
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04);
  padding: 20px;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title h2 {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
}

.actions {
  display: flex;
  gap: 8px;
}
</style>
