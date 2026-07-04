<template>
  <div class="filter-section">
    <a-form layout="vertical" :model="filters">
      <a-row :gutter="16">
        <a-col :xs="24" :sm="12" :md="8" :lg="4">
          <a-form-item label="客户">
            <KeywordAutoComplete v-model="filters.keyword" placeholder="公司名称/公司 ID" width="100%" />
          </a-form-item>
        </a-col>
        <a-col :xs="24" :sm="12" :md="8" :lg="4">
          <a-form-item label="账号类型">
            <a-select v-model="filters.account_type" placeholder="请选择" allow-clear style="width: 100%">
              <a-option value="正式账号">正式账号</a-option>
              <a-option value="测试账号">测试账号</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :xs="24" :sm="12" :md="8" :lg="4">
          <a-form-item label="行业类型">
            <a-select v-model="filters.industry" placeholder="请选择行业类型" allow-clear multiple :max-tag-count="1" style="width: 100%">
              <a-option v-for="item in industryTypes" :key="item.id" :value="item.name">{{ item.name }}</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :xs="24" :sm="12" :md="8" :lg="4">
          <a-form-item label="充值日期">
            <a-range-picker v-model="filters.recharge_date" style="width: 100%" />
          </a-form-item>
        </a-col>
      </a-row>
      <a-row :gutter="16">
        <a-col :xs="24" :sm="12" :md="8" :lg="4">
          <a-form-item label="重点客户">
            <a-select v-model="filters.is_key_customer" placeholder="请选择" allow-clear style="width: 100%">
              <a-option :value="true">是</a-option>
              <a-option :value="false">否</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :xs="24" :sm="12" :md="8" :lg="4">
          <a-form-item label="房产客户">
            <a-select v-model="filters.is_real_estate" placeholder="请选择" allow-clear style="width: 100%">
              <a-option :value="true">是</a-option>
              <a-option :value="false">否</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :xs="24" :sm="12" :md="8" :lg="4">
          <a-form-item label="结算类型">
            <a-select v-model="filters.settlement_type" placeholder="请选择" allow-clear style="width: 100%">
              <a-option value="prepaid">预付费</a-option>
              <a-option value="postpaid">后付费</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :xs="24" :sm="12" :md="8" :lg="4">
          <a-form-item label="&nbsp;">
            <a-space>
              <a-button type="primary" @click="emit('search')">查询</a-button>
              <a-button @click="emit('reset')">重置</a-button>
            </a-space>
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>

    <a-collapse class="advanced-filter-collapse">
      <a-collapse-item key="1" header="高级筛选">
        <a-row :gutter="16">
          <a-col :xs="24" :sm="12" :md="8" :lg="6">
            <a-form-item label="销售经理">
              <a-select v-model="advancedFilters.manager_id" placeholder="请选择" allow-clear style="width: 100%">
                <a-option v-for="m in managers" :key="m.id" :value="m.id">{{ m.username }}</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="6">
            <a-form-item label="销售顾问">
              <a-select v-model="advancedFilters.sales_manager_id" placeholder="请选择" allow-clear style="width: 100%">
                <a-option v-for="m in managers" :key="m.id" :value="m.id">{{ m.username }}</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="6">
            <a-form-item label="客户标签">
              <TagSelector v-model="advancedFilters.tag_ids" :tags="tagOptions" multiple />
            </a-form-item>
          </a-col>
        </a-row>
      </a-collapse-item>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import KeywordAutoComplete from '@/components/KeywordAutoComplete.vue'
import TagSelector from '@/components/TagSelector.vue'
import type { IndustryType, Tag, User } from '@/types'

interface Filters {
  keyword: string
  recharge_date: string[]
  industry: string[]
  account_type: string
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
  tagOptions: Tag[]
  managers: User[]
}>()

const emit = defineEmits<{
  search: []
  reset: []
}>()
</script>

<style scoped>
.filter-section { background: #fff; padding: 20px 24px; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.advanced-filter-collapse { margin-top: 16px; }
</style>
