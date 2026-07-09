<template>
  <div class="compact-table-shell cop-table-shell">
    <slot />
  </div>
</template>

<style scoped>
.compact-table-shell :deep(.arco-table-th) {
  background: var(--cop-bg);
  color: var(--cop-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 10px 12px;
  border-bottom: 1px solid var(--cop-line);
}
.compact-table-shell :deep(.arco-table-td) {
  padding: 8px 12px;
  font-size: 13px;
  border-bottom: 1px solid var(--cop-line);
}
.compact-table-shell :deep(.arco-table-row:hover .arco-table-td) {
  background: var(--cop-bg);
}
.compact-table-shell :deep(.arco-table) {
  border-radius: var(--cop-radius);
  overflow: hidden;
}
</style>