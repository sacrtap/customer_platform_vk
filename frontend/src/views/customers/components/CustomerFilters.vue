<template>
  <div class="filter-card">
    <!-- 筛选行: 搜索框 + FilterDropdowns + 筛选按钮 -->
    <div class="filters">
      <div class="search-input-wrap">
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          v-model="filters.keyword"
          type="text"
          placeholder="搜索客户名称 / 公司 ID"
          @keydown.enter="handleSearch"
        />
      </div>

      <FilterDropdown
        label="行业"
        v-model="industryValue"
        :options="industryOptions"
        multiple
        @apply="handleSearch"
      />
      <FilterDropdown
        label="规模等级"
        v-model="filters.scale_level"
        :options="scaleOptions"
        @apply="handleSearch"
      />
      <FilterDropdown
        label="消费等级"
        v-model="filters.consume_level"
        :options="consumeOptions"
        @apply="handleSearch"
      />
      <FilterDropdown
        label="运营经理"
        v-model="managerValue"
        :options="managerOptions"
        @apply="handleSearch"
      />
      <FilterDropdown
        label="销售经理"
        v-model="salesValue"
        :options="salesOptions"
        @apply="handleSearch"
      />

      <button type="button" class="btn primary" @click="handleSearch">筛选</button>
    </div>

    <!-- 高级筛选折叠区 -->
    <a-collapse class="advanced-filter-collapse">
      <a-collapse-item>
        <template #header>
          <div class="advanced-filter-toggle">
            <span>高级筛选</span>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
              aria-hidden="true"
            >
              <path
                fill-rule="evenodd"
                d="M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z"
              />
            </svg>
          </div>
        </template>
        <a-form layout="vertical" :model="advancedFilters">
          <a-row :gutter="16">
            <a-col :xs="24" :sm="12" :md="8" :lg="6">
              <a-form-item label="重点客户">
                <a-select
                  v-model="filters.is_key_customer"
                  placeholder="请选择"
                  allow-clear
                >
                  <a-option :value="true">是</a-option>
                  <a-option :value="false">否</a-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :md="8" :lg="6">
              <a-form-item label="房产客户">
                <a-select
                  v-model="filters.is_real_estate"
                  placeholder="请选择"
                  allow-clear
                >
                  <a-option :value="true">是</a-option>
                  <a-option :value="false">否</a-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :md="8" :lg="6">
              <a-form-item label="结算方式">
                <a-select
                  v-model="filters.settlement_type"
                  placeholder="请选择"
                  allow-clear
                >
                  <a-option value="prepaid">预付费</a-option>
                  <a-option value="postpaid">后付费</a-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :md="8" :lg="6">
              <a-form-item label="&nbsp;">
                <a-button type="primary" @click="handleAdvancedSearch">
                  应用高级筛选
                </a-button>
              </a-form-item>
            </a-col>
          </a-row>
        </a-form>
      </a-collapse-item>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { IndustryType } from '@/types'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'

interface Filters {
  keyword: string
  industry: string
  scale_level: string
  consume_level: string
  is_key_customer: boolean | null
  is_real_estate: boolean | null
  settlement_type: string
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
}>()

const emit = defineEmits<{
  search: []
  reset: []
  'advanced-search': []
}>()

// 筛选选项 computed
const industryOptions = computed(() =>
  props.industryTypes.map((it) => ({ label: it.name, value: it.name }))
)

const scaleOptions = [
  { label: 'S（超大型）', value: 'S' },
  { label: 'A（大型）', value: 'A' },
  { label: 'B（中型）', value: 'B' },
  { label: 'C（小型）', value: 'C' },
  { label: 'D（微型）', value: 'D' },
]

const consumeOptions = [
  { label: 'S（高价值）', value: 'S' },
  { label: 'A（高消费）', value: 'A' },
  { label: 'B（中消费）', value: 'B' },
  { label: 'C（低消费）', value: 'C' },
  { label: '未消费', value: 'none' },
]

const managerOptions = computed(() =>
  (props.managers as Array<{ id: number; real_name: string | null }>).map(
    (m) => ({ label: m.real_name || `#${m.id}`, value: String(m.id) })
  )
)

const salesOptions = computed(() =>
  (props.managers as Array<{ id: number; real_name: string | null }>).map(
    (m) => ({ label: m.real_name || `#${m.id}`, value: String(m.id) })
  )
)

// 行业多选转换 (API 用逗号分隔字符串)
const industryValue = computed({
  get: () => {
    const v = filters.value.industry
    return v ? v.split(',') : []
  },
  set: (val: string[]) => {
    filters.value.industry = val.join(',')
  },
})

// 运营经理 (单选 string -> number | null)
const managerValue = computed({
  get: () => filters.value.keyword || '',
  set: (_val: string) => {
    // manager handled via advancedFilters.manager_id
  },
})

// 销售经理 (单选 string -> number | null)
const salesValue = computed({
  get: () => '',
  set: (_val: string) => {},
})

const handleSearch = () => emit('search')
const handleReset = () => emit('reset')
const handleAdvancedSearch = () => emit('advanced-search')
</script>

<style scoped>
.filter-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  padding: 18px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: white;
  min-width: 220px;
}
.search-input-wrap:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1);
}
.search-input-wrap input {
  border: none;
  outline: none;
  font-size: 13px;
  flex: 1;
  background: transparent;
}

.btn.primary {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: var(--primary);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn.primary:hover {
  background: var(--primary-hover);
  transform: translateY(-1px);
}

/* 高级筛选折叠面板 */
.advanced-filter-collapse {
  margin-top: 12px;
  border: none;
  background: transparent;
}
.advanced-filter-collapse :deep(.arco-collapse-item) {
  border: none;
}
.advanced-filter-collapse :deep(.arco-collapse-item-header) {
  padding: 8px 0;
  border: none;
}
.advanced-filter-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
  cursor: pointer;
}

.filter-card :deep(.arco-form-item) {
  margin-bottom: 12px;
}
.filter-card :deep(.arco-form-item-label) {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}
.filter-card :deep(.arco-select-view-single) {
  border-radius: var(--radius-sm);
}

@media (max-width: 1100px) {
  .filters {
    flex-direction: column;
    align-items: stretch;
  }
  .search-input-wrap {
    width: 100%;
  }
}
</style>
