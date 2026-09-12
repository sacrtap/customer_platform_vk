<template>
  <transition name="slide-down">
    <div v-if="selectedCount > 0" class="batch-toolbar">
      <span class="batch-count"
        >已选择 <b>{{ selectedCount }}</b> 项</span
      >
      <button class="btn" @click="emit('batchAction', 'recharge')">批量充值</button>
      <button class="btn" disabled title="即将上线">
        批量导出 <span class="soon-badge">即将上线</span>
      </button>
      <button class="btn" @click="emit('clear')">取消选择</button>
    </div>
  </transition>
</template>

<script setup lang="ts">
defineProps<{ selectedCount: number }>()

const emit = defineEmits<{
  batchAction: [action: string]
  clear: []
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

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.soon-badge {
  font-size: 10px;
  font-weight: 600;
  color: #f59e0b;
  background: #fef3c7;
  padding: 1px 6px;
  border-radius: 999px;
  margin-left: 4px;
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.25s ease-out;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
