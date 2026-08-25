<template>
  <div class="filters-container">
    <!-- 第一行：基础筛选 + 筛选按钮 + 更多按钮 -->
    <div class="filters-row">
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

      <!-- 筛选按钮 + 更多按钮 固定在首行右侧 -->
      <div class="filters-actions">
        <button type="button" class="btn-more" @click="toggleMore">
          {{ showMore ? '收起' : '更多' }}
          <span class="more-arrow" :class="{ rotated: showMore }">▾</span>
        </button>
        <button type="button" class="btn primary" @click="handleSearch">筛选</button>
      </div>
    </div>

    <!-- 第二行：更多筛选（折行显示，左对齐） -->
    <transition name="expand">
      <div v-if="showMore" class="filters-row more-row">
        <FilterDropdown
          v-model="filters.erp_system"
          label="ERP系统"
          :options="erpSystemOptions"
          @apply="handleSearch"
        />
        <FilterDropdown
          v-model="filters.cooperation_status"
          label="合作状态"
          :options="cooperationStatusOptions"
          @apply="handleSearch"
        />
        <FilterDropdown
          v-model="filters.settlement_type"
          label="结算方式"
          :options="settlementTypeOptions"
          @apply="handleSearch"
        />
      </div>
    </transition>

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
import { ref, computed } from 'vue'
import type { IndustryType, ErpSystem, CooperationStatus } from '@/types'
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
  erp_system: string
  cooperation_status: string
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
  erpSystems: ErpSystem[]
  cooperationStatuses: CooperationStatus[]
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

// ========== 更多筛选展开/收起 ==========
const showMore = ref(false)
const toggleMore = () => {
  showMore.value = !showMore.value
}

// 筛选选项
const accountTypeOptions = [
  { label: '正式账号', value: '正式账号' },
  { label: '客户测试账号', value: '客户测试账号' },
  { label: '内部账号', value: '内部账号' },
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

const erpSystemOptions = computed(() =>
  props.erpSystems.map((es) => ({ label: es.name, value: es.value }))
)

const cooperationStatusOptions = computed(() =>
  props.cooperationStatuses.map((cs) => ({ label: cs.name, value: cs.value }))
)

const settlementTypeOptions = [
  { label: '预付费', value: 'prepaid' },
  { label: '后付费', value: 'postpaid' },
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

.filters-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.more-row {
  padding-top: 8px;
  border-top: 1px dashed var(--soft, #e2e8f0);
  margin-top: 8px;
}

/* 筛选按钮 + 更多按钮 固定在首行右侧 */
.filters-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-left: auto;
  flex-shrink: 0;
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
  white-space: nowrap;
}
.btn.primary:hover {
  background: #1e40af;
}

.btn-more {
  padding: 9px 12px;
  border: 1px solid var(--soft, #e2e8f0);
  border-radius: 12px;
  background: white;
  color: var(--ink, #1e293b);
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition:
    background 0.2s,
    border-color 0.2s;
  white-space: nowrap;
}
.btn-more:hover {
  background: var(--bg, #f8fafc);
  border-color: var(--primary, #3b82f6);
  color: var(--primary, #3b82f6);
}

.more-arrow {
  font-size: 11px;
  transition: transform 0.2s ease;
}
.more-arrow.rotated {
  transform: rotate(180deg);
}

/* 展开/收起动画 */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  margin-top: 0;
  padding-top: 0;
  border-top-color: transparent;
}
.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 60px;
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
  .filters-row {
    flex-direction: column;
    align-items: stretch;
  }
  .filters-actions {
    margin-left: 0;
    justify-content: flex-end;
  }
  .search-input-wrap {
    width: 100%;
    max-width: none;
  }
}
</style>
