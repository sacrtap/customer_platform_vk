<template>
  <section class="chart-card cop-card">
    <div class="chart-card__header">
      <h2 class="chart-card__title">{{ title }}</h2>
      <slot name="meta" />
    </div>
    <div class="chart-card__content">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title: string
}>()
</script>

<style scoped>
.chart-card {
  padding: 0;
  overflow: hidden;
}
.chart-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--cop-line);
}
.chart-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--cop-ink);
}
.chart-card__content {
  padding: 16px 18px;
  min-height: 200px;
}
</style>