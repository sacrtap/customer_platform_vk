<template>
  <transition name="fade">
    <div v-if="selectedCount > 0" class="batch-toolbar">
      <span class="batch-count"
        >已选择 <b>{{ selectedCount }}</b> 项</span
      >
      <button class="btn" @click="emit('batchAction', 'edit')">批量编辑</button>
      <button class="btn" @click="emit('batchAction', 'assign')">分配负责人</button>
      <button class="btn" @click="emit('batchAction', 'export')">批量导出</button>
      <button class="btn" @click="$emit('addTag')">设标签</button>
    </div>
  </transition>
</template>

<script setup lang="ts">
defineProps<{ selectedCount: number }>()

const emit = defineEmits<{
  batchAction: [action: string]
  addTag: []
}>()
</script>

<style scoped>
.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  margin-bottom: 12px;
}

.batch-count {
  font-size: 13px;
  font-weight: 700;
  color: #1d4ed8;
  margin-right: auto;
}

.batch-count b {
  font-weight: 850;
}

.btn {
  padding: 6px 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: white;
  color: var(--ink);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}

.btn:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.fade-enter-active,
.fade-leave-active {
  transition: all 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
