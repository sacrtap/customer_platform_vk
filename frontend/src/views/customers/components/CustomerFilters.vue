<template>
    <!-- 筛选区域 -->
    <div class="filter-section">
      <a-form layout="vertical" :model="filters">
        <a-row :gutter="16">
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="关键词">
              <KeywordAutoComplete
                v-model="filters.keyword"
                placeholder="公司名称/公司 ID"
                @press-enter="handleSearch"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="账号类型">
              <a-select v-model="filters.account_type" placeholder="请选择" allow-clear>
                <a-option value="正式账号">正式账号</a-option>
                <a-option value="测试账号">测试账号</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="行业类型">
              <a-select
                v-model="filters.industry"
                placeholder="请选择行业类型"
                allow-clear
                multiple
                :max-tag-count="1"
                :max-tag-placeholder="(count: number) => `+${count}`"
              >
                <a-option v-for="item in industryTypes" :key="item.id" :value="item.name">
                  {{ item.name }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="重点客户">
              <a-select v-model="filters.is_key_customer" placeholder="请选择" allow-clear>
                <a-option :value="true">是</a-option>
                <a-option :value="false">否</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="房产客户">
              <a-select v-model="filters.is_real_estate" placeholder="请选择" allow-clear>
                <a-option :value="true">是</a-option>
                <a-option :value="false">否</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="结算方式">
              <a-select v-model="filters.settlement_type" placeholder="请选择" allow-clear>
                <a-option value="prepaid">预付费</a-option>
                <a-option value="postpaid">后付费</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="&nbsp;">
              <a-space>
                <a-button type="primary" @click="handleSearch">查询</a-button>
                <a-button @click="handleReset">重置</a-button>
              </a-space>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <!-- 高级筛选区域 -->
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
                <a-form-item label="运营经理">
                  <a-select
                    v-model="advancedFilters.manager_id"
                    placeholder="请选择运营经理"
                    allow-clear
                    :loading="managersLoading"
                  >
                    <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
                      {{ manager.real_name || manager.username }}
                    </a-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :xs="24" :sm="12" :md="8" :lg="6">
                <a-form-item label="商务经理">
                  <a-select
                    v-model="advancedFilters.sales_manager_id"
                    placeholder="请选择商务经理"
                    allow-clear
                    :loading="managersLoading"
                  >
                    <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
                      {{ manager.real_name || manager.username }}
                    </a-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :xs="24" :sm="12" :md="8" :lg="6">
                <a-form-item label="标签筛选">
                  <a-select
                    v-model="advancedFilters.tag_ids"
                    placeholder="选择标签"
                    multiple
                    allow-clear
                    :loading="tagsLoading"
                  >
                    <a-option v-for="tag in customerTags" :key="tag.id" :value="tag.id">
                      {{ tag.name }}
                    </a-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :xs="24" :sm="12" :md="8" :lg="6">
                <a-form-item label="&nbsp;">
                  <a-button type="primary" @click="handleAdvancedSearch">应用高级筛选</a-button>
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>
        </a-collapse-item>
      </a-collapse>
    </div>
</template>

<script setup lang="ts">
import type { IndustryType } from '@/types'
import KeywordAutoComplete from '@/components/KeywordAutoComplete.vue'

interface Filters {
  keyword: string
  account_type: string
  industry: string[]
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
const advancedFilters = defineModel<AdvancedFilters>('advancedFilters', { required: true })
defineProps<{
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

const handleSearch = () => emit('search')
const handleReset = () => emit('reset')
const handleAdvancedSearch = () => emit('advanced-search')
</script>
