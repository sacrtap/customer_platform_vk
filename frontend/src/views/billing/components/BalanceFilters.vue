<template>
  <div class="filters-container">
    <!-- 第一行：基础筛选 + 按钮组（与客户管理页布局一致） -->
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

      <!-- 按钮组固定在首行右侧 -->
      <div class="filters-actions">
        <button type="button" class="btn-more" @click="toggleMore">
          {{ showMore ? '收起' : '更多' }}
          <span class="more-arrow" :class="{ rotated: showMore }">▾</span>
        </button>
        <button v-if="empty" type="button" class="btn" @click="handleReset">清除筛选条件</button>
        <button type="button" class="btn primary" @click="handleSearch">筛选</button>
      </div>
    </div>

    <!-- 第二行：更多筛选（折行显示，左对齐，对齐客户管理页，去掉「标签」） -->
    <transition name="expand">
      <div v-if="showMore" class="filters-row more-row">
        <FilterDropdown
          v-model="settlementEnabledValue"
          label="是否结算"
          :options="BOOLEAN_FILTER_OPTIONS"
          @apply="handleSearch"
        />
        <FilterDropdown
          v-model="autoInitiateValue"
          label="自动发起结算"
          :options="BOOLEAN_FILTER_OPTIONS"
          @apply="handleSearch"
        />
        <FilterDropdown
          v-model="keyCustomerValue"
          label="是否重点客户"
          :options="BOOLEAN_FILTER_OPTIONS"
          @apply="handleSearch"
        />
        <FilterDropdown
          v-model="realEstateValue"
          label="是否房产客户"
          :options="BOOLEAN_FILTER_OPTIONS"
          @apply="handleSearch"
        />
        <FilterDropdown
          v-model="disabledValue"
          label="是否停用"
          :options="BOOLEAN_FILTER_OPTIONS"
          @apply="handleSearch"
        />
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
      </div>
    </transition>

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
import { ref, computed } from 'vue'
import type { IndustryType, ErpSystem, CooperationStatus } from '@/types'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import { BOOLEAN_FILTER_OPTIONS } from '@/constants/customerOptions'
import CustomerSearchInput from '@/views/customers/components/CustomerSearchInput.vue'
import { BALANCE_RANGE_OPTIONS } from '@/composables/useBalance'

interface Filters {
  keyword: string
  recharge_date: string[]
  industry: string[]
  account_type: string
  is_key_customer: boolean | null
  is_real_estate: boolean | null
  is_settlement_enabled: boolean | null
  auto_initiate_settlement: boolean | null
  is_disabled: boolean | null
  settlement_type: string
  erp_system: string
  cooperation_status: string
  /** KPI 卡片联动：prepaid = 非后付费（含未设置），postpaid = 后付费 */
  settlement_group: '' | 'prepaid' | 'postpaid'
  balance_range: string
}

interface AdvancedFilters {
  manager_id: number | null
  sales_manager_id: number | null
}

const filters = defineModel<Filters>('filters', { required: true })
const advancedFilters = defineModel<AdvancedFilters>('advancedFilters', { required: true })

const props = defineProps<{
  industryTypes: IndustryType[]
  erpSystems: ErpSystem[]
  cooperationStatuses: CooperationStatus[]
  managers: Array<Record<string, unknown>>
  activeKpiBadge?: string
  /** 列表为空时显示「清除筛选条件」（当前筛选无结果） */
  empty?: boolean
}>()

const emit = defineEmits<{
  search: []
  reset: []
  'clear-kpi': []
}>()

// 更多筛选展开状态
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

const settlementOptions = [
  { label: '预付费', value: 'prepaid' },
  { label: '后付费', value: 'postpaid' },
]

const balanceRangeOptions = BALANCE_RANGE_OPTIONS.map((o) => ({
  label: o.label,
  value: o.value,
}))

const industryOptions = computed(() =>
  props.industryTypes.map((it) => ({ label: it.name, value: it.name }))
)

const managerOptions = computed(() =>
  props.managers.map((m) => ({ label: String(m.real_name ?? m.id), value: String(m.id) }))
)

const salesOptions = computed(() =>
  props.managers.map((m) => ({ label: String(m.real_name ?? m.id), value: String(m.id) }))
)

const erpSystemOptions = computed(() =>
  props.erpSystems.map((es) => ({ label: es.name, value: es.value }))
)

const cooperationStatusOptions = computed(() =>
  props.cooperationStatuses.map((cs) => ({ label: cs.name, value: cs.value }))
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
    filters.value.industry = val
  },
})

// 运营经理 (number | null -> string)
const managerValue = computed({
  get: () => (advancedFilters.value.manager_id ? String(advancedFilters.value.manager_id) : ''),
  set: (val: string) => {
    advancedFilters.value.manager_id = val ? Number(val) : null
  },
})

// 销售经理 (number | null -> string)
const salesValue = computed({
  get: () =>
    advancedFilters.value.sales_manager_id ? String(advancedFilters.value.sales_manager_id) : '',
  set: (val: string) => {
    advancedFilters.value.sales_manager_id = val ? Number(val) : null
  },
})

// 自动发起结算 (boolean | null -> string)
const autoInitiateValue = computed({
  get: () =>
    filters.value.auto_initiate_settlement === null
      ? ''
      : String(filters.value.auto_initiate_settlement),
  set: (val: string) => {
    filters.value.auto_initiate_settlement = val === '' ? null : val === 'true'
  },
})

// 是否停用 (boolean | null -> string)
const disabledValue = computed({
  get: () => (filters.value.is_disabled === null ? '' : String(filters.value.is_disabled)),
  set: (val: string) => {
    filters.value.is_disabled = val === '' ? null : val === 'true'
  },
})

// 是否结算 (boolean | null -> string)
const settlementEnabledValue = computed({
  get: () =>
    filters.value.is_settlement_enabled === null ? '' : String(filters.value.is_settlement_enabled),
  set: (val: string) => {
    filters.value.is_settlement_enabled = val === '' ? null : val === 'true'
  },
})

// 重点客户 (boolean | null -> string)
const keyCustomerValue = computed({
  get: () => (filters.value.is_key_customer === null ? '' : String(filters.value.is_key_customer)),
  set: (val: string) => {
    filters.value.is_key_customer = val === '' ? null : val === 'true'
  },
})

// 房产客户 (boolean | null -> string)
const realEstateValue = computed({
  get: () => (filters.value.is_real_estate === null ? '' : String(filters.value.is_real_estate)),
  set: (val: string) => {
    filters.value.is_real_estate = val === '' ? null : val === 'true'
  },
})

const handleSearch = () => emit('search')
const handleReset = () => emit('reset')
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

/* 按钮组固定在首行右侧（与客户管理页一致） */
.filters-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-left: auto;
  flex-shrink: 0;
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
  white-space: nowrap;
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
}
</style>
