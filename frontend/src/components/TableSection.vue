<template>
  <div class="table-section">
    <slot />
  </div>
</template>

<script setup lang="ts">
// 表格区域容器组件 — 来源: design.md 4.3
</script>

<style scoped>
.table-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--line);
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04);
  overflow: hidden;
}

/* Arco 表格表头样式覆盖 — 对齐 design.md 4.3 */
:deep(.arco-table-th) {
  background-color: var(--bg) !important;
  color: #334155 !important;
  font-weight: 600 !important;
  font-size: 12px !important;
}

:deep(.arco-table-tr:hover .arco-table-td) {
  background-color: #F8FBFF !important;
}
</style>
