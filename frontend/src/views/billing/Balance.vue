<template>
  <div class="balance-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>余额管理</h1>
        <p class="header-subtitle">客户余额充值与管理</p>
      </div>
      <div class="header-actions">
        <a-button v-if="can('billing:recharge')" type="primary" @click="openRechargeModal()">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"
              />
            </svg>
          </template>
          新建充值
        </a-button>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="filter-section">
      <a-form layout="vertical" :model="filters">
        <a-row :gutter="16">
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="客户">
              <CustomerAutoComplete
                v-model="filters.customer_id"
                placeholder="请输入客户名称搜索"
                width="100%"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="6">
            <a-form-item label="充值时间">
              <a-range-picker
                v-model="filters.recharge_date"
                placeholder="['开始日期', '结束日期']"
                style="width: 100%"
                format="YYYY-MM-DD"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="行业类型">
              <a-select
                v-model="filters.industry"
                placeholder="请选择行业类型"
                allow-clear
                multiple
              >
                <a-option
                  v-for="item in industryTypes"
                  :key="item.id"
                  :value="item.name"
                >
                  {{ item.name }}
                </a-option>
              </a-select>
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
            <a-form-item label="重点客户">
              <a-select v-model="filters.is_key_customer" placeholder="请选择" allow-clear>
                <a-option :value="true">是</a-option>
                <a-option :value="false">否</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="6">
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

    <!-- 表格 -->
    <div class="table-section">
      <a-table
        :columns="columns"
        :data="balances"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="handlePageChange"
        @sorter-change="handleSort"
      >
        <template #balance="{ record }">
          <div class="balance-info">
            <div>总额：{{ formatCurrency(record.total_amount) }}</div>
            <div class="balance-detail">
              <span class="real">实充：{{ formatCurrency(record.real_amount) }}</span>
              <span class="bonus">赠送：{{ formatCurrency(record.bonus_amount) }}</span>
            </div>
          </div>
        </template>
        <template #used="{ record }">
          <div>
            {{ formatCurrency(record.used_total) }}
            <div class="used-detail">
              <span class="used-real">实：{{ formatCurrency(record.used_real) }}</span>
              <span class="used-bonus">赠：{{ formatCurrency(record.used_bonus) }}</span>
            </div>
          </div>
        </template>
        <template #last_recharge_at="{ record }">
          {{ record.last_recharge_at ? formatLastRechargeTime(record.last_recharge_at) : '-' }}
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button
              v-if="can('billing:recharge')"
              type="primary"
              size="small"
              @click="openRechargeModal(record)"
              >充值</a-button
            >
            <a-button type="text" size="small" @click="viewRechargeRecords(record)">记录</a-button>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无余额数据" description="点击「新建充值」为客户充值">
            <template #action>
              <a-button v-if="can('billing:recharge')" type="primary" @click="openRechargeModal()"
                >新建充值</a-button
              >
            </template>
          </EmptyState>
        </template>
      </a-table>
    </div>

    <!-- 充值对话框 -->
    <a-modal
      v-model:visible="rechargeModalVisible"
      title="客户充值"
      :confirm-loading="rechargeLoading"
      @before-ok="handleRecharge"
      @cancel="rechargeModalVisible = false"
    >
      <a-form ref="rechargeFormRef" :model="rechargeForm" layout="vertical">
        <a-form-item field="customer_id" label="客户" required>
          <CustomerAutoComplete
            v-model="rechargeForm.customer_id"
            placeholder="请输入客户名称搜索"
            width="100%"
          />
        </a-form-item>
        <a-form-item field="real_amount" label="充值金额" required>
          <a-input-number
            v-model="rechargeForm.real_amount"
            placeholder="请输入充值金额"
            style="width: 100%"
            :min="0.01"
            :precision="2"
            :step="100"
          />
        </a-form-item>
        <a-form-item field="bonus_amount" label="赠送金额">
          <a-input-number
            v-model="rechargeForm.bonus_amount"
            placeholder="请输入赠送金额"
            style="width: 100%"
            :min="0"
            :precision="2"
            :step="100"
          />
        </a-form-item>
        <a-form-item field="remark" label="备注">
          <a-textarea
            v-model="rechargeForm.remark"
            placeholder="请输入备注"
            :max-length="200"
            show-word-limit
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 充值记录对话框 -->
    <a-modal
      v-model:visible="recordModalVisible"
      title="充值记录"
      :footer="false"
      width="800px"
      @ok="recordModalVisible = false"
      @cancel="recordModalVisible = false"
    >
      <a-table
        :columns="recordColumns"
        :data="rechargeRecords"
        :loading="recordLoading"
        row-key="id"
        :pagination="recordPagination"
        @page-change="handleRecordPageChange"
      >
        <template #amount="{ record }">
          <div>
            {{ formatCurrency(record.total_amount) }}
            <div class="amount-detail">
              <span class="real">实：{{ formatCurrency(record.real_amount) }}</span>
              <span class="bonus">赠：{{ formatCurrency(record.bonus_amount) }}</span>
            </div>
          </div>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'

import {
  getBalances,
  recharge,
  getRechargeRecords,
  type Balance,
  type RechargeRecord,
} from '@/api/billing'
import { getIndustryTypes } from '@/api/customers'
import { getTags } from '@/api/tags'
import { getManagers } from '@/api/users'
import EmptyState from '@/components/EmptyState.vue'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
import { formatCurrency } from '@/utils/formatters'
import type { IndustryType } from '@/types'

// 格式化充值时间（与结算单列表保持一致：含秒）
const formatLastRechargeTime = (dateStr: string): string => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// 默认筛选值（工厂函数，确保每次调用返回新引用）
const createDefaultFilters = () => ({
  customer_id: undefined as number | undefined,
  recharge_date: [] as string[],
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  account_type: '正式账号',
  is_key_customer: null as boolean | null,
})

const filters = reactive(createDefaultFilters())

// 高级筛选条件
const advancedFilters = reactive({
  manager_id: null as number | null,
  sales_manager_id: null as number | null,
  tag_ids: [] as number[],
})

// 下拉选项数据
const managersLoading = ref(false)
const managers = ref<Array<Record<string, unknown>>>([])
const tagsLoading = ref(false)
const customerTags = ref<Array<Record<string, unknown>>>([])
const industryTypes = ref<IndustryType[]>([])

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

// 数据
const loading = ref(false)
const balances = ref<Balance[]>([])

// 排序状态
const sortState = reactive({
  sort_by: 'company_id',
  sort_order: 'ascend' as 'ascend' | 'descend' | '',
})

// 表格列定义
const columns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 100, sortable: { sortDirections: ['ascend', 'descend'] }, ellipsis: true, tooltip: true },
  { title: '客户名称', dataIndex: 'customer_name', width: 200, sortable: { sortDirections: ['ascend', 'descend'] }, ellipsis: true, tooltip: true },
  { title: '余额', dataIndex: 'total_amount', slotName: 'balance', width: 280, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '已消耗', dataIndex: 'used_total', slotName: 'used', width: 200, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '最新充值时间', dataIndex: 'last_recharge_at', slotName: 'last_recharge_at', width: 180, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '操作', slotName: 'action', width: 200, fixed: 'right' as const },
]

// 充值对话框相关
const rechargeModalVisible = ref(false)
const rechargeLoading = ref(false)
const selectedBalance = ref<Balance | null>(null)
const rechargeForm = reactive({
  customer_id: undefined as number | undefined,
  real_amount: null as number | null,
  bonus_amount: null as number | null,
  remark: '',
})

// 充值记录对话框相关
const recordModalVisible = ref(false)
const recordLoading = ref(false)
const rechargeRecords = ref<RechargeRecord[]>([])
const recordPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
})
const currentRecordCustomerId = ref<number | null>(null)

// 充值记录表格列
const recordColumns = [
  { title: '充值时间', dataIndex: 'created_at', width: 180 },
  { title: '金额', slotName: 'amount', width: 200 },
  { title: '备注', dataIndex: 'remark', width: 200 },
]

// 加载余额列表
const loadBalances = async () => {
  loading.value = true
  try {
    // 将前端的 ascend/descend 转换为后端期望的 asc/desc
    const backendSortOrder = sortState.sort_order === 'ascend' ? 'asc' : sortState.sort_order === 'descend' ? 'desc' : 'asc'

    const params: {
      page: number
      page_size: number
      customer_id?: number
      account_type?: string
      industry?: string
      manager_id?: number
      sales_manager_id?: number
      recharge_date_from?: string
      recharge_date_to?: string
      tag_ids?: string
      is_key_customer?: boolean
      sort_by: string
      sort_order: 'asc' | 'desc'
    } = {
      page: pagination.current,
      page_size: pagination.pageSize,
      sort_by: sortState.sort_by,
      sort_order: backendSortOrder,
    }
    if (filters.customer_id) params.customer_id = filters.customer_id
    if (filters.account_type) params.account_type = filters.account_type
    if (filters.industry && filters.industry.length > 0) params.industry = filters.industry.join(',')
    if (filters.recharge_date && filters.recharge_date.length === 2) {
      params.recharge_date_from = filters.recharge_date[0]
      params.recharge_date_to = filters.recharge_date[1]
    }
    if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id
    if (advancedFilters.sales_manager_id) params.sales_manager_id = advancedFilters.sales_manager_id
    if (advancedFilters.tag_ids && advancedFilters.tag_ids.length > 0) {
      params.tag_ids = advancedFilters.tag_ids.join(',')
    }
    if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer

    const res = await getBalances(params)
    balances.value = res.data.list || []
    pagination.total = res.data.total || 0
    pagination.current = res.data.page || 1
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载余额列表失败')
  } finally {
    loading.value = false
  }
}

// 处理排序
const handleSort = (dataIndex: string, direction: 'ascend' | 'descend' | '') => {
  if (!direction) {
    // 取消排序时恢复默认
    sortState.sort_by = 'company_id'
    sortState.sort_order = 'ascend'
  } else {
    sortState.sort_by = dataIndex
    sortState.sort_order = direction
  }
  pagination.current = 1 // 重置到第一页
  loadBalances()
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  loadBalances()
}

// 重置
const handleReset = () => {
  Object.assign(filters, createDefaultFilters())
  advancedFilters.manager_id = null
  advancedFilters.sales_manager_id = null
  advancedFilters.tag_ids = []
  pagination.current = 1
  loadBalances()
}

// 高级筛选搜索
const handleAdvancedSearch = () => {
  pagination.current = 1
  loadBalances()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  loadBalances()
}

// 打开充值对话框
const openRechargeModal = (balance?: Balance) => {
  selectedBalance.value = balance || null
  rechargeForm.customer_id = balance ? balance.customer_id : undefined
  rechargeForm.real_amount = null
  rechargeForm.bonus_amount = null
  rechargeForm.remark = ''
  rechargeModalVisible.value = true
}

// 处理充值
const handleRecharge = async () => {
  if (!rechargeForm.customer_id) {
    Message.error('请选择客户')
    return false
  }
  if (!rechargeForm.real_amount || rechargeForm.real_amount <= 0) {
    Message.error('请输入有效的充值金额')
    return false
  }

  rechargeLoading.value = true
  try {
    const res = await recharge({
      customer_id: rechargeForm.customer_id!,
      real_amount: rechargeForm.real_amount!,
      bonus_amount: rechargeForm.bonus_amount || undefined,
      remark: rechargeForm.remark || undefined,
    })
    Message.success('充值成功')

    // 局部更新：找到对应客户行，更新余额数据
    const customerId = res.data.customer_id
    const balanceData = res.data.balance
    if (balanceData) {
      const targetIndex = balances.value.findIndex(b => b.customer_id === customerId)
      if (targetIndex !== -1) {
        balances.value[targetIndex] = {
          ...balances.value[targetIndex],
          total_amount: balanceData.total_amount,
          real_amount: balanceData.real_amount,
          bonus_amount: balanceData.bonus_amount,
          used_total: balanceData.used_total,
          used_real: balanceData.used_real,
          used_bonus: balanceData.used_bonus,
          last_recharge_at: new Date().toISOString(),
        }
      }
    }

    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '充值失败')
    return false
  } finally {
    rechargeLoading.value = false
  }
}

// 查看充值记录
const viewRechargeRecords = async (record: Balance) => {
  currentRecordCustomerId.value = record.customer_id
  recordModalVisible.value = true
  recordLoading.value = true
  try {
    const res = await getRechargeRecords({
      customer_id: record.customer_id,
      page: recordPagination.current,
      page_size: recordPagination.pageSize,
    })
    rechargeRecords.value = res.data.list || res.data.items || []
    recordPagination.total = res.data.total || 0
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载充值记录失败')
  } finally {
    recordLoading.value = false
  }
}

// 加载充值记录
const loadRechargeRecords = async () => {
  if (!currentRecordCustomerId.value) return

  recordLoading.value = true
  try {
    const res = await getRechargeRecords({
      customer_id: currentRecordCustomerId.value,
      page: recordPagination.current,
      page_size: recordPagination.pageSize,
    })
    rechargeRecords.value = res.data.list || []
    recordPagination.total = res.data.total || 0
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载充值记录失败')
  } finally {
    recordLoading.value = false
  }
}

// 充值记录分页变化
const handleRecordPageChange = (page: number) => {
  recordPagination.current = page
  loadRechargeRecords()
}

onMounted(() => {
  loadBalances()
  // 加载高级筛选项数据
  loadManagers()
  loadCustomerTags()
  loadIndustryTypesData()
})

// 加载运营经理列表
const loadManagers = async () => {
  managersLoading.value = true
  try {
    const res = await getManagers()
    managers.value = res.data?.list || res.data || []
  } catch (error: unknown) {
    console.error('加载运营经理失败:', error)
  } finally {
    managersLoading.value = false
  }
}

// 加载客户标签列表
const loadCustomerTags = async () => {
  tagsLoading.value = true
  try {
    const res = await getTags({ type: 'customer', page_size: 100 })
    customerTags.value = res.data?.list || []
  } catch (error: unknown) {
    console.error('加载标签失败:', error)
  } finally {
    tagsLoading.value = false
  }
}

// 加载行业类型
const loadIndustryTypesData = async () => {
  try {
    const res = await getIndustryTypes()
    industryTypes.value = res.data?.data || res.data || []
  } catch (error) {
    console.error('Failed to load industry types:', error)
  }
}
</script>

<style scoped>
.balance-management-page {
  padding: 0; /* 移除 padding，由 Dashboard 统一提供 */
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-9: #2f3645;
  --neutral-10: #1d2330;
  --primary-6: #0369a1;
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

.filter-section .arco-form-item {
  margin-bottom: 0;
}

.filter-section .arco-select,
.filter-section .arco-input,
.filter-section .arco-picker {
  width: 100%;
}

.advanced-filter-collapse {
  margin-top: 16px;
}

.advanced-filter-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.advanced-filter-toggle svg {
  transition: transform 0.2s;
}

.table-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.balance-info {
  font-size: 14px;
}

.balance-detail {
  display: flex;
  gap: 16px;
  margin-top: 4px;
  font-size: 12px;
}

.balance-detail .real,
.amount-detail .real,
.used-detail .used-real {
  color: var(--primary-6);
}

.balance-detail .bonus,
.amount-detail .bonus,
.used-detail .used-bonus {
  color: #22c55e;
}

.used-detail,
.amount-detail {
  display: flex;
  gap: 12px;
  margin-top: 4px;
  font-size: 12px;
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
