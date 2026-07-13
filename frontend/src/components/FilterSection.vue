<template>
  <div class="filter-section">
    <slot />
  </div>
</template>

<script setup lang="ts">
// 筛选区域容器组件 — 来源: design.md 4.2
</script>

<style scoped>
.filter-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--line);
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04);
  margin-bottom: 24px;
}
</style>
