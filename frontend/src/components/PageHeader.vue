<template>
  <div class="page-header">
    <div class="header-info">
      <span v-if="eyebrow" class="eyebrow">{{ eyebrow }}</span>
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="desc">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  eyebrow?: string
  title: string
  subtitle?: string
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 12px;
}

.header-info h1 {
  font-size: 26px;
  font-weight: 850;
  margin: 4px 0;
  color: var(--ink);
}

.desc {
  color: var(--muted);
  margin: 0;
  max-width: 760px;
  font-size: 14px;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 640px) {
  .header-info {
    width: 100%;
  }

  .actions {
    width: 100%;
  }

  .header-info h1 {
    font-size: 22px;
  }

  .desc {
    font-size: 13px;
  }
}
</style>
