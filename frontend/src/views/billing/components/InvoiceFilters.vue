<template>
  <div class="filter-section">
    <a-form layout="vertical" :model="filters">
      <a-row :gutter="16">
        <a-col :xs="24" :sm="12" :md="8" :lg="4">
          <a-form-item label="客户">
            <KeywordAutoComplete v-model="filters.keyword" placeholder="公司名称/公司 ID" :width="'100%'" />
          </a-form-item>
        </a-col>
        <a-col :xs="24" :sm="12" :md="8" :lg="4">
          <a-form-item label="状态">
            <a-select v-model="filters.status" placeholder="请选择" allow-clear style="width: 100%">
              <a-option value="draft">草稿</a-option>
              <a-option value="pending_customer">待客户确认</a-option>
              <a-option value="customer_confirmed">客户已确认</a-option>
              <a-option value="paid">已付款</a-option>
              <a-option value="completed">已完成</a-option>
              <a-option value="cancelled">已取消</a-option>
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
  </div>
</template>

<script setup lang="ts">
import KeywordAutoComplete from '@/components/KeywordAutoComplete.vue'

interface Filters {
  keyword: string
  status: string
}

const filters = defineModel<Filters>('filters', { required: true })

const emit = defineEmits<{
  search: []
  reset: []
}>()
</script>

<style scoped>
.filter-section { background: #fff; padding: 20px 24px; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
</style>
