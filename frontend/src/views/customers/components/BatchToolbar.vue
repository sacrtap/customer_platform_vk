<template>
  <transition name="fade">
    <div v-if="selectedCount > 0" class="batch-toolbar">
      <div class="batch-info">
        <svg
          class="batch-icon"
          width="20"
          height="20"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          stroke-width="2"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <span>已选 {{ selectedCount }} 个客户</span>
      </div>

      <div class="batch-actions">
        <button class="btn-batch" @click="emit('batchAction', 'assign')">
          分配运营经理
        </button>
        <button class="btn-batch" @click="emit('batchAction', 'setLevel')">
          设置等级
        </button>
        <button class="btn-batch" @click="$emit('addTag')">
          打标签
        </button>
        <button class="btn-batch" @click="emit('batchAction', 'export')">
          导出数据
        </button>
        <button class="btn-batch" @click="emit('batchAction', 'email')">
          群发邮件
        </button>
        <button class="btn-batch danger" @click="emit('batchAction', 'delete')">
          批量删除
        </button>
      </div>
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
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  background: #eff6ff;
  border-bottom: 1px solid var(--line);
  border-radius: 0 0 0 0;
  animation: slideDown 0.25s ease-out;
}

.batch-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--primary);
}

.batch-icon {
  color: var(--primary);
  font-weight: 600;
}

.batch-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.btn-batch {
  padding: 8px 16px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: white;
  color: var(--ink);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-batch:hover {
  border-color: var(--primary);
  color: var(--primary);
}
.btn-batch.danger {
  color: var(--red);
  border-color: #fecaca;
}
.btn-batch.danger:hover {
  background: #fef2f2;
  border-color: var(--red);
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

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
