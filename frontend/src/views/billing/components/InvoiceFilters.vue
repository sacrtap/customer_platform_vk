<template>
  <div class="filters-container">
    <div class="filters">
      <CustomerSearchInput v-model="filters.keyword" @search="emit('search')" />
      <FilterDropdown
        v-model="filters.status"
        label="状态"
        :options="statusOptions"
        @apply="emit('search')"
      />
      <button type="button" class="btn primary" @click="emit('search')">筛选</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import CustomerSearchInput from '@/views/customers/components/CustomerSearchInput.vue'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'

interface Filters {
  keyword: string
  status: string
}

const filters = defineModel<Filters>('filters', { required: true })

const emit = defineEmits<{
  search: []
  reset: []
}>()

const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '待客户确认', value: 'pending_customer' },
  { label: '客户已确认', value: 'customer_confirmed' },
  { label: '已付款', value: 'paid' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'cancelled' },
]
</script>

<style scoped>
.filters-container {
  margin-bottom: 12px;
}

.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.btn.primary {
  padding: 9px 12px;
  border: 1px solid var(--primary);
  border-radius: 12px;
  background: var(--primary);
  color: white;
  font-weight: 700;
  cursor: pointer;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}
.btn.primary:hover {
  background: #1e40af;
}

@media (max-width: 1100px) {
  .filters {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
