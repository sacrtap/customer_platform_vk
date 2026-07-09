<template>
  <section class="data-section cop-card">
    <header class="data-section__header">
      <div class="data-section__title-group">
        <h2 class="data-section__title">{{ title }}</h2>
        <span v-if="subtitle" class="data-section__subtitle">{{ subtitle }}</span>
        <span v-if="count !== undefined" class="data-section__count">共 {{ count }} 条</span>
      </div>
      <div v-if="$slots.actions" class="data-section__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="data-section__body">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="data-section__footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
  count?: number
}>()
</script>

<style scoped>
.data-section {
  padding: 0;
}
.data-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid var(--cop-line);
}
.data-section__title-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.data-section__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--cop-ink);
}
.data-section__subtitle {
  color: var(--cop-muted);
  font-size: 13px;
}
.data-section__count {
  color: var(--cop-muted);
  font-size: 12px;
  padding: 2px 8px;
  background: var(--cop-bg);
  border-radius: 10px;
}
.data-section__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.data-section__body {
  padding: 16px;
}
.data-section__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid var(--cop-line);
  background: var(--cop-bg);
  border-radius: 0 0 var(--cop-radius) var(--cop-radius);
}
</style>