<template>
  <div class="batch-toolbar">
    <span class="batch-count"
      >已选择 <b>{{ count }}</b> 项</span
    >
    <slot />
  </div>
</template>

<script setup lang="ts">
// 批量操作工具栏 — 来源: design.md 4.6
defineProps<{
  count: number
}>()
</script>

<style scoped>
.batch-toolbar {
  margin-bottom: 16px;
  padding: 10px 14px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.batch-count {
  font-size: 13px;
  font-weight: 700;
  color: #1d4ed8;
  margin-right: auto;
}
</style>
