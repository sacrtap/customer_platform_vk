<template>
  <div class="pagination">
    <span class="page-total">共 {{ total.toLocaleString() }} 条</span>
    <div class="pagination-right">
      <span class="page-size">
        每页
        <select class="page-size-select" :value="pageSize" @change="onPageSizeChange">
          <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}</option>
        </select>
        条
      </span>
      <div class="page-controls">
        <button class="page-btn" :disabled="current <= 1" @click="onPageChange(current - 1)">
          ‹
        </button>
        <button
          v-for="p in displayPages"
          :key="p"
          class="page-btn"
          :class="{ active: p === current, ellipsis: p === -1 }"
          :disabled="p === -1"
          @click="p > 0 && onPageChange(p)"
        >
          {{ p === -1 ? '…' : p }}
        </button>
        <button
          class="page-btn"
          :disabled="current >= totalPages"
          @click="onPageChange(current + 1)"
        >
          ›
        </button>
      </div>
      <span class="page-jump">
        跳至
        <input
          type="number"
          class="page-jump-input"
          :value="current"
          :min="1"
          :max="totalPages"
          @keydown.enter="onJumpPage(($event.target as HTMLInputElement).value)"
        />
        页
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    current: number
    pageSize: number
    total: number
    pageSizeOptions?: number[]
  }>(),
  {
    pageSizeOptions: () => [10, 20, 50, 100],
  }
)

const emit = defineEmits<{
  pageChange: [page: number]
  pageSizeChange: [size: number]
}>()

const totalPages = computed(() => Math.ceil(props.total / props.pageSize) || 1)

const displayPages = computed(() => {
  const current = props.current
  const total = totalPages.value
  const pages: number[] = []

  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i)
  } else {
    pages.push(1)
    if (current > 3) pages.push(-1)
    const start = Math.max(2, current - 1)
    const end = Math.min(total - 2, current + 1)
    for (let i = start; i <= end; i++) pages.push(i)
    if (end < total - 2) pages.push(-1)
    pages.push(total)
  }
  return pages
})

const onPageChange = (page: number) => {
  if (page < 1 || page > totalPages.value) return
  emit('pageChange', page)
}

const onPageSizeChange = (e: Event) => {
  emit('pageSizeChange', Number((e.target as HTMLSelectElement).value))
}

const onJumpPage = (val: string) => {
  const page = parseInt(val, 10)
  if (page >= 1 && page <= totalPages.value) {
    onPageChange(page)
  }
}
</script>

<style scoped>
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  gap: 12px;
  flex-wrap: wrap;
}

.page-total {
  font-size: 13px;
  color: #64748b;
}

.pagination-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-size {
  font-size: 13px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-size-select {
  padding: 4px 8px;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 6px;
  background: var(--panel, #fff);
  color: var(--ink, #0f172a);
  font-size: 13px;
  cursor: pointer;
}

.page-controls {
  display: flex;
  gap: 4px;
  align-items: center;
}

.page-btn {
  min-width: 30px;
  height: 30px;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 6px;
  background: var(--panel, #fff);
  color: var(--ink, #0f172a);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.page-btn:hover:not(:disabled) {
  border-color: var(--primary, #1d4ed8);
  color: var(--primary, #1d4ed8);
}

.page-btn.active {
  background: var(--primary, #1d4ed8);
  border-color: var(--primary, #1d4ed8);
  color: #fff;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-btn.ellipsis {
  border: none;
  background: none;
  cursor: default;
  opacity: 1;
}

.page-jump {
  font-size: 13px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-jump-input {
  width: 50px;
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 6px;
  text-align: center;
  font-size: 13px;
  color: var(--ink, #0f172a);
}

.page-jump-input:focus {
  outline: none;
  border-color: var(--primary, #1d4ed8);
}

@media (max-width: 768px) {
  .pagination {
    flex-direction: column;
    align-items: stretch;
  }

  .pagination-right {
    flex-wrap: wrap;
    gap: 8px;
  }
}

@media (max-width: 640px) {
  .page-size,
  .page-jump {
    display: none;
  }
}
</style>
