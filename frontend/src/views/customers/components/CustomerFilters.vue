<template>
  <div class="filters-container">
    <!-- 筛选行: 搜索框 + FilterDropdowns + 筛选按钮 -->
    <div class="filters">
      <CustomerSearchInput v-model="filters.keyword" @search="handleSearch" />

      <FilterDropdown
        v-model="filters.account_type"
        label="账号类型"
        :options="accountTypeOptions"
        @apply="handleSearch"
      />
      <FilterDropdown
        v-model="industryValue"
        label="行业"
        :options="industryOptions"
        multiple
        @apply="handleSearch"
      />
      <FilterDropdown
        v-model="filters.scale_level"
        label="规模等级"
        :options="scaleOptions"
        @apply="handleSearch"
      />
      <FilterDropdown
        v-model="filters.consume_level"
        label="消费等级"
        :options="consumeOptions"
        @apply="handleSearch"
      />
      <FilterDropdown
        v-model="managerValue"
        label="运营经理"
        :options="managerOptions"
        @apply="handleSearch"
      />
      <FilterDropdown
        v-model="salesValue"
        label="销售经理"
        :options="salesOptions"
        @apply="handleSearch"
      />

      <button type="button" class="btn primary" @click="handleSearch">筛选</button>
    </div>

    <!-- KPI 筛选徽章 -->
    <div v-if="activeKpiBadge" class="kpi-badge-row">
      <span class="kpi-filter-badge">
        {{ activeKpiBadge }}
        <span class="badge-close" @click="clearKpiBadge">✕</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { IndustryType } from '@/types'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import CustomerSearchInput from './CustomerSearchInput.vue'

interface Filters {
  keyword: string
  account_type: string
  industry: string[]
  scale_level: string
  consume_level: string
  is_key_customer: boolean | null
  is_real_estate: boolean | null
  settlement_type: string
  incomplete_profile: boolean
  mine: boolean
}

interface AdvancedFilters {
  manager_id: number | null
  sales_manager_id: number | null
  tag_ids: number[]
}

const filters = defineModel<Filters>('filters', { required: true })
const advancedFilters = defineModel<AdvancedFilters>('advancedFilters', {
  required: true,
})

const props = defineProps<{
  industryTypes: IndustryType[]
  managers: Array<Record<string, unknown>>
  customerTags: Array<Record<string, unknown>>
  managersLoading: boolean
  tagsLoading: boolean
  activeKpiBadge?: string
}>()

const emit = defineEmits<{
  search: []
  reset: []
  'advanced-search': []
  'clear-kpi': []
}>()

// 筛选选项 computed
const accountTypeOptions = [
  { label: '正式账号', value: '正式账号' },
  { label: '测试账号', value: '测试账号' },
]

const industryOptions = computed(() =>
  props.industryTypes.map((it) => ({ label: it.name, value: it.name }))
)

const scaleOptions = [
  { label: 'S（超大型）', value: 'S' },
  { label: 'A（大型）', value: 'A' },
  { label: 'B（中型）', value: 'B' },
  { label: 'C（小型）', value: 'C' },
  { label: 'D（微型）', value: 'D' },
  { label: 'E（极小型）', value: 'E' },
]

const consumeOptions = [
  { label: 'C1 - 100万', value: 'C1' },
  { label: 'C2 - 50万', value: 'C2' },
  { label: 'C3 - 25万', value: 'C3' },
  { label: 'C4 - 12万', value: 'C4' },
  { label: 'C5 - 6万', value: 'C5' },
  { label: 'C6 - 6万以下', value: 'C6' },
]

const managerOptions = computed(() =>
  (props.managers as Array<{ id: number; real_name: string | null }>).map((m) => ({
    label: m.real_name || `#${m.id}`,
    value: String(m.id),
  }))
)

const salesOptions = computed(() =>
  (props.managers as Array<{ id: number; real_name: string | null }>).map((m) => ({
    label: m.real_name || `#${m.id}`,
    value: String(m.id),
  }))
)

// 行业多选转换：composables 中存为 string[]，API 请求时 join(',')
const industryValue = computed({
  get: () => {
    const v = filters.value.industry
    if (!v) return []
    if (Array.isArray(v)) return v
    return (v as string).split(',')
  },
  set: (val: string[]) => {
    filters.value.industry = val as unknown as string[]
  },
})

// 运营经理 (单选 string -> number | null)
const managerValue = computed({
  get: () => {
    if (advancedFilters.value.manager_id) return String(advancedFilters.value.manager_id)
    return ''
  },
  set: (val: string) => {
    advancedFilters.value.manager_id = val ? Number(val) : null
  },
})

// 销售经理 (单选 string -> number | null)
const salesValue = computed({
  get: () => {
    if (advancedFilters.value.sales_manager_id)
      return String(advancedFilters.value.sales_manager_id)
    return ''
  },
  set: (val: string) => {
    advancedFilters.value.sales_manager_id = val ? Number(val) : null
  },
})

const handleSearch = () => emit('search')
const clearKpiBadge = () => emit('clear-kpi')
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

/* KPI 筛选徽章 */
.kpi-badge-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.kpi-filter-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  background: #dbeafe;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}
.badge-close {
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.2s;
  font-size: 14px;
}
.badge-close:hover {
  opacity: 1;
}

@media (max-width: 1100px) {
  .filters {
    flex-direction: column;
    align-items: stretch;
  }
  .search-input-wrap {
    width: 100%;
    max-width: none;
  }
}
</style>
