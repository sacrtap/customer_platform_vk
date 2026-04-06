<template>
  <div class="customer-list-page">
    <div class="page-header">
      <div class="header-title">
        <h1>客户管理</h1>
        <p class="header-subtitle">统一客户基础信息与画像数据管理</p>
      </div>
      <div class="header-actions">
        <a-button type="primary" @click="$message.info('新建客户开发中')">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"/>
            </svg>
          </template>
          新建客户
        </a-button>
        <a-button @click="$message.info('导入功能开发中')">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/>
              <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/>
            </svg>
          </template>
          导入
        </a-button>
        <a-button @click="$message.info('导出功能开发中')">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/>
              <path d="M7.646 4.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1-.708.708L8.5 5.707V14.5a.5.5 0 0 1-1 0V5.707L5.354 7.854a.5.5 0 1 1-.708-.708l3-3z"/>
            </svg>
          </template>
          导出
        </a-button>
      </div>
    </div>
    
    <!-- 筛选区域 -->
    <div class="filter-section">
      <a-form layout="inline" :model="filters">
        <a-form-item label="关键词">
          <a-input v-model="filters.keyword" placeholder="公司名称/公司 ID" style="width: 200px">
            <template #prefix>
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/>
              </svg>
            </template>
          </a-input>
        </a-form-item>
        <a-form-item label="业务类型">
          <a-select v-model="filters.business_type" placeholder="请选择" style="width: 150px" allow-clear>
            <a-option value="A">A 类业务</a-option>
            <a-option value="B">B 类业务</a-option>
            <a-option value="C">C 类业务</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="客户等级">
          <a-select v-model="filters.customer_level" placeholder="请选择" style="width: 150px" allow-clear>
            <a-option value="KA">KA</a-option>
            <a-option value="SKA">SKA</a-option>
            <a-option value="普通">普通</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="重点客户">
          <a-select v-model="filters.is_key_customer" placeholder="请选择" style="width: 120px" allow-clear>
            <a-option :value="true">是</a-option>
            <a-option :value="false">否</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="handleSearch">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </div>
    
    <!-- 表格 -->
    <div class="table-section">
      <a-table :columns="columns" :data="data" :loading="loading" row-key="id" :pagination="pagination" @page-change="handlePageChange">
        <template #action>
          <a-space>
            <a-button type="text" size="small" @click="$message.info('查看开发中')">查看</a-button>
            <a-button type="text" size="small" @click="$message.info('编辑开发中')">编辑</a-button>
            <a-button type="text" size="small" @click="$message.info('画像开发中')">画像</a-button>
            <a-popconfirm content="确认删除？" @ok="$message.info('删除开发中')">
              <a-button type="text" size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'

const filters = reactive({
  keyword: '',
  business_type: '',
  customer_level: '',
  is_key_customer: null as boolean | null,
})

const loading = ref(false)

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 100,
  showTotal: true,
  showPageSize: true,
})

const columns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 120 },
  { title: '客户名称', dataIndex: 'name', width: 200 },
  { title: '业务类型', dataIndex: 'business_type', width: 100 },
  { title: '客户等级', dataIndex: 'customer_level', width: 100 },
  { title: '结算方式', dataIndex: 'settlement_type', width: 100 },
  { title: '运营经理', dataIndex: 'manager', width: 120 },
  { title: '重点客户', dataIndex: 'is_key_customer', width: 80 },
  { title: '操作', slotName: 'action', width: 280, fixed: 'right' as const },
]

const data = ref([
  { id: 1, company_id: 'COMP001', name: 'XX 科技有限公司', business_type: 'A', customer_level: 'KA', settlement_type: '预付费', manager: '张三', is_key_customer: true },
  { id: 2, company_id: 'COMP002', name: 'YY 集团有限公司', business_type: 'B', customer_level: 'SKA', settlement_type: '后付费', manager: '李四', is_key_customer: true },
  { id: 3, company_id: 'COMP003', name: 'ZZ 创新股份', business_type: 'A', customer_level: '普通', settlement_type: '预付费', manager: '王五', is_key_customer: false },
  { id: 4, company_id: 'COMP004', name: 'AA 数字科技', business_type: 'C', customer_level: '普通', settlement_type: '预付费', manager: '赵六', is_key_customer: false },
])

const handleSearch = () => {
  loading.value = true
  setTimeout(() => {
    loading.value = false
  }, 500)
}

const handleReset = () => {
  filters.keyword = ''
  filters.business_type = ''
  filters.customer_level = ''
  filters.is_key_customer = null
}

const handlePageChange = (page: number) => {
  pagination.current = page
}
</script>

<style scoped>
.customer-list-page {
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-9: #2f3645;
  --neutral-10: #1d2330;
  --primary-6: #0369A1;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-10);
  margin-bottom: 8px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--neutral-6);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.filter-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  margin-bottom: 24px;
}

.table-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

:deep(.arco-table) {
  font-size: 14px;
}

:deep(.arco-table th) {
  background: var(--neutral-1);
  color: var(--neutral-6);
  font-weight: 600;
}

:deep(.arco-table td) {
  color: var(--neutral-7);
}

:deep(.arco-table tr:hover td) {
  background: var(--neutral-1);
}
</style>
