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
        v-model="filters.settlement_type"
        label="结算类型"
        :options="settlementOptions"
        @apply="handleSearch"
      />
      <FilterDropdown
        v-model="filters.balance_range"
        label="余额范围"
        :options="balanceRangeOptions"
        @apply="handleSearch"
      />
      <FilterDropdown
        v-model="keyCustomerValue"
        label="重点客户"
        :options="boolOptions"
        @apply="handleSearch"
      />
      <FilterDropdown
        v-model="realEstateValue"
        label="房产客户"
        :options="boolOptions"
        @apply="handleSearch"
      />

      <button type="button" class="btn primary" @click="handleSearch">筛选</button>
      <button type="button" class="btn" @click="handleReset">重置</button>
    </div>

    <!-- KPI 筛选徽章 -->
    <div v-if="activeKpiBadge" class="kpi-badge-row">
      <span class="kpi-filter-badge">
        {{ activeKpiBadge }}
        <span class="badge-close" @click="emit('clear-kpi')">✕</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { IndustryType } from '@/types'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import CustomerSearchInput from '@/views/customers/components/CustomerSearchInput.vue'
import { BALANCE_RANGE_OPTIONS } from '@/composables/useBalance'

interface Filters {
  keyword: string
  recharge_date: string[]
  industry: string[]
  account_type: string
  is_key_customer: boolean | null
  is_real_estate: boolean | null
  settlement_type: string
  balance_range: string
}

interface AdvancedFilters {
  manager_id: number | null
  sales_manager_id: number | null
  tag_ids: number[]
}

const filters = defineModel<Filters>('filters', { required: true })
defineModel<AdvancedFilters>('advancedFilters', { required: true })

const props = defineProps<{
  industryTypes: IndustryType[]
  tagOptions: Array<Record<string, unknown>>
  managers: Array<Record<string, unknown>>
  activeKpiBadge?: string
}>()

const emit = defineEmits<{
  search: []
  reset: []
  'clear-kpi': []
}>()

// 筛选选项
const accountTypeOptions = [
  { label: '正式账号', value: '正式账号' },
  { label: '测试账号', value: '测试账号' },
]

const settlementOptions = [
  { label: '预付费', value: 'prepaid' },
  { label: '后付费', value: 'postpaid' },
]

const balanceRangeOptions = BALANCE_RANGE_OPTIONS.map((o) => ({
  label: o.label,
  value: o.value,
}))

const boolOptions = [
  { label: '是', value: 'true' },
  { label: '否', value: 'false' },
]

const industryOptions = computed(() =>
  props.industryTypes.map((it) => ({ label: it.name, value: it.name }))
)

// 行业多选转换
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

// 重点客户 (boolean | null -> string)
const keyCustomerValue = computed({
  get: () => {
    if (filters.value.is_key_customer === true) return 'true'
    if (filters.value.is_key_customer === false) return 'false'
    return ''
  },
  set: (val: string) => {
    if (val === 'true') filters.value.is_key_customer = true
    else if (val === 'false') filters.value.is_key_customer = false
    else filters.value.is_key_customer = null
  },
})

// 房产客户 (boolean | null -> string)
const realEstateValue = computed({
  get: () => {
    if (filters.value.is_real_estate === true) return 'true'
    if (filters.value.is_real_estate === false) return 'false'
    return ''
  },
  set: (val: string) => {
    if (val === 'true') filters.value.is_real_estate = true
    else if (val === 'false') filters.value.is_real_estate = false
    else filters.value.is_real_estate = null
  },
})

const handleSearch = () => emit('search')
const handleReset = () => emit('reset')
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

.btn {
  padding: 9px 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: white;
  color: var(--ink);
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
.btn.primary {
  border-color: var(--primary);
  background: var(--primary);
  color: white;
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
}
</style>
