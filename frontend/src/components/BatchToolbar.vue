<template>
  <div class="batch-toolbar">
    <a-tag color="arcoblue" size="large">
      已选择 {{ count }} 条
    </a-tag>
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
  padding: 12px 16px;
  background: rgba(29, 78, 216, .06);
  border: 1px solid rgba(29, 78, 216, .15);
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
