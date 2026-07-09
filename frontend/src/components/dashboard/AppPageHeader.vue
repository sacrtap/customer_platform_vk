<template>
  <header class="app-page-header">
    <div>
      <p v-if="eyebrow" class="app-page-header__eyebrow">{{ eyebrow }}</p>
      <h1 class="app-page-header__title">{{ title }}</h1>
      <p v-if="description" class="app-page-header__description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="app-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  eyebrow?: string
  description?: string
}>()
</script>

<style scoped>
.app-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.app-page-header__eyebrow {
  margin: 0 0 4px;
  color: var(--cop-primary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.app-page-header__title {
  margin: 0;
  color: var(--cop-ink);
  font-size: 26px;
  font-weight: 850;
  line-height: 1.2;
}
.app-page-header__description {
  margin: 6px 0 0;
  color: var(--cop-muted);
  max-width: 760px;
}
.app-page-header__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
@media (max-width: 768px) {
  .app-page-header {
    flex-direction: column;
  }
  .app-page-header__actions {
    width: 100%;
  }
}
</style>