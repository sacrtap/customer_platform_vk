<template>
  <div class="customer-list-page">
    <div class="page-header">
      <div class="header-title">
        <h1>客户管理</h1>
        <p class="header-subtitle">统一客户基础信息与画像数据管理</p>
      </div>
      <div class="header-actions">
        <a-button v-if="can('customers:create')" type="primary" @click="openCreateModal">
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
          新建客户
        </a-button>
        <a-button v-if="can('customers:import')" @click="openImportModal">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"
              />
              <path
                d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"
              />
            </svg>
          </template>
          导入
        </a-button>
        <a-button v-if="can('customers:export')" @click="handleExport">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"
              />
              <path
                d="M7.646 4.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1-.708.708L8.5 5.707V14.5a.5.5 0 0 1-1 0V5.707L5.354 7.854a.5.5 0 1 1-.708-.708l3-3z"
              />
            </svg>
          </template>
          导出
        </a-button>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="filter-section">
      <a-form layout="vertical" :model="filters">
        <a-row :gutter="16">
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="关键词">
              <a-input v-model="filters.keyword" placeholder="公司名称/公司 ID" @press-enter="handleSearch">
                <template #prefix>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    fill="currentColor"
                    viewBox="0 0 16 16"
                  >
                    <path
                      d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"
                    />
                  </svg>
                </template>
              </a-input>
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
            <a-form-item label="重点客户">
              <a-select v-model="filters.is_key_customer" placeholder="请选择" allow-clear>
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

    <!-- 表格 -->
    <div class="table-section">
      <a-table
        :columns="columns"
        :data="customers"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        :scroll="{ x: 'max-content' }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @sorter-change="handleSort"
      >
        <template #name="{ record }">
          <div class="name-cell">
            <span v-if="record.is_key_customer" class="key-customer-badge" title="重点客户">★</span>
            <span class="name-text">{{ record.name }}</span>
          </div>
        </template>
        <template #createdAt="{ record }">
          {{ formatDateTime(record.created_at) }}
        </template>
        <template #settlementType="{ record }">
          {{ getSettlementTypeName(record.settlement_type) }}
        </template>
        <template #manager="{ record }">
          {{ getManagerName(record.manager_id) }}
        </template>
        <template #salesManager="{ record }">
          {{ getSalesManagerName(record.sales_manager_id) }}
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button type="primary" size="small" @click="viewCustomer(record.id)">查看</a-button>
            <a-button v-if="can('customers:edit')" type="text" size="small" @click="openEditModal(record)">编辑</a-button>
            <a-dropdown>
              <a-button type="text" size="small">更多</a-button>
              <template #content>
                <a-doption @click="viewProfile(record.id)">画像</a-doption>
                <a-doption v-if="can('customers:delete')" style="color: #ff4d4f" @click="() => handleDelete(record.id)"
                  >删除</a-doption
                >
              </template>
            </a-dropdown>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无客户数据" description="点击「新建客户」添加第一个客户">
            <template #action>
              <a-button v-if="can('customers:create')" type="primary" @click="openCreateModal">新建客户</a-button>
            </template>
          </EmptyState>
        </template>
      </a-table>
    </div>

    <!-- 新建/编辑客户对话框 -->
    <a-modal
      v-model:visible="customerModalVisible"
      :title="isEditMode ? '编辑客户' : '新建客户'"
      :confirm-loading="customerModalLoading"
      width="600px"
      @before-ok="handleCustomerSubmit"
      @cancel="handleCustomerModalCancel"
    >
      <a-form
        ref="customerFormRef"
        :model="customerForm"
        :rules="customerFormRules"
        layout="vertical"
        validate-trigger="['blur', 'change']"
      >
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="company_id" label="公司 ID" required>
              <a-input
                v-model="customerForm.company_id"
                placeholder="请输入公司 ID"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="name" label="客户名称" required>
              <a-input v-model="customerForm.name" placeholder="请输入客户名称" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item field="email" label="邮箱">
          <a-input v-model="customerForm.email" placeholder="请输入邮箱" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="account_type" label="账号类型">
              <a-select
                v-model="customerForm.account_type"
                placeholder="请选择账号类型"
                allow-clear
              >
                <a-option value="正式账号">正式账号</a-option>
                <a-option value="测试账号">测试账号</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="industry" label="行业类型">
              <a-select
                v-model="customerForm.industry"
                placeholder="请选择行业类型"
                allow-clear
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
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="settlement_type" label="结算方式">
              <a-select
                v-model="customerForm.settlement_type"
                placeholder="请选择结算方式"
                allow-clear
              >
                <a-option value="prepaid">预付费</a-option>
                <a-option value="postpaid">后付费</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="settlement_cycle" label="结算周期">
              <a-select
                v-model="customerForm.settlement_cycle"
                placeholder="请选择结算周期"
                allow-clear
              >
                <a-option value="日结">日结</a-option>
                <a-option value="周结">周结</a-option>
                <a-option value="月结">月结</a-option>
                <a-option value="季结">季结</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="is_key_customer" label="重点客户">
              <a-switch v-model="customerForm.is_key_customer" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item field="manager_id" label="运营经理">
          <a-select
            v-model="customerForm.manager_id"
            placeholder="请选择运营经理"
            allow-clear
            :loading="managersLoading"
          >
            <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
              {{ manager.real_name || manager.username }}
            </a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="sales_manager_id" label="商务经理">
          <a-select
            v-model="customerForm.sales_manager_id"
            placeholder="请选择商务经理"
            allow-clear
            :loading="managersLoading"
          >
            <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
              {{ manager.real_name || manager.username }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 导入对话框 -->
    <a-modal
      v-model:visible="importModalVisible"
      title="导入客户"
      :confirm-loading="importLoading"
      width="560px"
      @before-ok="handleImportSubmit"
      @cancel="importModalVisible = false"
    >
      <div class="import-modal-content">
        <a-alert type="info" style="margin-bottom: 20px">
          请下载模板文件，填写后上传 Excel 文件进行导入
          <template #action>
            <a-button type="text" size="small" @click="downloadTemplate">
              <template #icon>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="7 10 12 15 17 10"/>
                  <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
              </template>
              下载模板
            </a-button>
          </template>
        </a-alert>

        <div class="upload-area" @click="triggerFileInput" @drop.prevent="handleFileDrop" @dragover.prevent @dragenter.prevent>
          <input
            ref="fileInputRef"
            type="file"
            accept=".xlsx,.xls"
            class="file-input-hidden"
            @change="handleFileInputChange"
          />
          <div v-if="!importFile" class="upload-placeholder">
            <div class="upload-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>
            <div class="upload-text-primary">点击或拖拽文件到此处</div>
            <div class="upload-text-secondary">仅支持 .xlsx / .xls 格式的 Excel 文件</div>
          </div>
          <div v-else class="file-selected">
            <div class="file-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
            </div>
            <div class="file-info">
              <div class="file-name">{{ importFile.name }}</div>
              <div class="file-size">{{ formatFileSize(importFile.size) }}</div>
            </div>
            <div class="file-remove" @click.stop="removeFile">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </div>
          </div>
        </div>

        <div class="import-tips">
          <div class="tips-title">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="16" x2="12" y2="12"/>
              <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            导入须知
          </div>
          <ul class="tips-list">
            <li>请使用下载的模板文件填写客户信息</li>
            <li>确保必填字段（公司 ID、客户名称等）已填写</li>
            <li>单次导入建议不超过 1000 条数据</li>
          </ul>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import {
  getCustomers,
  deleteCustomer,
  exportCustomers,
  createCustomer,
  updateCustomer,
  importCustomers,
  downloadImportTemplate,
  getIndustryTypes,
} from '@/api/customers'
import { getTags } from '@/api/tags'
import { getManagers } from '@/api/users'
import EmptyState from '@/components/EmptyState.vue'
import { formatDateTime } from '@/utils/formatters'
import type { ImportResult, IndustryType, Customer } from '@/types'

const router = useRouter()
const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// 默认筛选值（工厂函数，确保每次调用返回新引用）
const createDefaultFilters = () => ({
  keyword: '',
  account_type: '正式账号',
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  is_key_customer: null as boolean | null,
  settlement_type: '',
})

const filters = reactive(createDefaultFilters())

const advancedFilters = reactive({
  manager_id: null as number | null,
  sales_manager_id: null as number | null,
  tag_ids: [] as number[],
})

const managersLoading = ref(false)
const managers = ref<Array<Record<string, unknown>>>([])
const tagsLoading = ref(false)
const customerTags = ref<Array<Record<string, unknown>>>([])
const industryTypes = ref<IndustryType[]>([])

const loading = ref(false)
const customers = ref<Customer[]>([])

// 排序状态
const sortState = reactive({
  sort_by: 'id',
  sort_order: 'ascend' as 'ascend' | 'descend' | '',
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const columns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 100, sortable: { sortDirections: ['ascend', 'descend'] }, ellipsis: true, tooltip: true },
  { title: '客户名称', dataIndex: 'name', slotName: 'name', width: 220, sortable: { sortDirections: ['ascend', 'descend'] }, ellipsis: true, tooltip: true },
  { title: '行业类型', dataIndex: 'industry', width: 120, sortable: { sortDirections: ['ascend', 'descend'] }, ellipsis: true, tooltip: true },
  { title: '结算方式', dataIndex: 'settlement_type', slotName: 'settlementType', width: 120, sortable: { sortDirections: ['ascend', 'descend'] }, ellipsis: true, tooltip: true },
  { title: '商务经理', dataIndex: 'sales_manager_id', slotName: 'salesManager', width: 130, sortable: { sortDirections: ['ascend', 'descend'] }, ellipsis: true, tooltip: true },
  { title: '运营经理', dataIndex: 'manager_id', slotName: 'manager', width: 130, sortable: { sortDirections: ['ascend', 'descend'] }, ellipsis: true, tooltip: true },
  { title: '创建时间', dataIndex: 'created_at', slotName: 'createdAt', width: 180, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '操作', slotName: 'action', width: 180, fixed: 'right' as const },
]

// 结算方式映射
const settlementTypeMap: Record<string, string> = {
  prepaid: '预付费',
  postpaid: '后付费',
}

// 获取结算方式显示名称
const getSettlementTypeName = (type: string | undefined): string => {
  if (!type) return '-'
  return settlementTypeMap[type] || type
}

// 获取运营经理显示名称
const getManagerName = (managerId: number | null | undefined): string => {
  if (!managerId) return '-'
  const manager = managers.value.find(m => m.id === managerId)
  return manager ? ((manager.real_name || manager.username) as string) : '-'
}

// 获取商务经理显示名称
const getSalesManagerName = (managerId: number | null | undefined): string => {
  if (!managerId) return '-'
  const manager = managers.value.find(m => m.id === managerId)
  return manager ? ((manager.real_name || manager.username) as string) : '-'
}

// 处理排序
const handleSort = (dataIndex: string, direction: 'ascend' | 'descend' | '') => {
  if (!direction) {
    // 取消排序时恢复默认
    sortState.sort_by = 'id'
    sortState.sort_order = 'ascend'
  } else {
    sortState.sort_by = dataIndex
    sortState.sort_order = direction
  }
  pagination.current = 1 // 重置到第一页
  loadCustomers()
}

// 加载客户列表
const loadCustomers = async () => {
  loading.value = true
  try {
    // 将前端的 ascend/descend 转换为后端期望的 asc/desc
    const backendSortOrder = sortState.sort_order === 'ascend' ? 'asc' : sortState.sort_order === 'descend' ? 'desc' : 'asc'

    const params: {
      page: number
      page_size: number
      keyword?: string
      account_type?: string
      industry?: string
      manager_id?: number
      sales_manager_id?: number
      is_key_customer?: boolean
      settlement_type?: string
      sort_by: string
      sort_order: 'asc' | 'desc'
    } = {
      page: pagination.current,
      page_size: pagination.pageSize,
      sort_by: sortState.sort_by,
      sort_order: backendSortOrder,
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.account_type) params.account_type = filters.account_type
    if (filters.industry && filters.industry.length > 0) params.industry = filters.industry.join(',')
    if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
    if (filters.settlement_type) params.settlement_type = filters.settlement_type
    if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id
    if (advancedFilters.sales_manager_id) params.sales_manager_id = advancedFilters.sales_manager_id

    const res = await getCustomers(params)
    customers.value = res.data.list || []
    pagination.total = res.data.total || 0
    pagination.current = res.data.page || 1
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  loadCustomers()
}

// 重置
const handleReset = () => {
  Object.assign(filters, createDefaultFilters())
  advancedFilters.manager_id = null
  advancedFilters.sales_manager_id = null
  advancedFilters.tag_ids = []
  pagination.current = 1
  loadCustomers()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  loadCustomers()
}

// 每页条数变化
const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1 // 切换条数时回到第一页
  loadCustomers()
}

// 删除客户
const handleDelete = async (id: number) => {
  await Modal.confirm({
    title: '确认删除',
    content: '删除后无法恢复，确定要删除该客户吗？',
    onOk: async () => {
      try {
        await deleteCustomer(id)
        Message.success('删除成功')
        loadCustomers()
      } catch (error: unknown) {
        Message.error((error as Error).message || '删除失败')
      }
    },
  })
}

// 高级筛选搜索
const handleAdvancedSearch = () => {
  pagination.current = 1
  loadCustomers()
}

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

// 导出客户
const handleExport = async () => {
  try {
    const params: Record<string, unknown> = {}
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.account_type) params.account_type = filters.account_type
    if (filters.industry && filters.industry.length > 0) params.industry = filters.industry.join(',')
    if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
    if (filters.settlement_type) params.settlement_type = filters.settlement_type
    if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id
    if (advancedFilters.sales_manager_id) params.sales_manager_id = advancedFilters.sales_manager_id

    const res = await exportCustomers(params)

    // 处理文件下载
    const blob = res.data as Blob
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `customers_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    Message.success('导出成功')
  } catch (error: unknown) {
    Message.error((error as Error).message || '导出失败')
  }
}

// ========== 新建/编辑客户 ==========
const customerModalVisible = ref(false)
const customerModalLoading = ref(false)
const customerFormRef = ref<FormInstance>()
const isEditMode = ref(false)
const editingCustomerId = ref<number | null>(null)

const customerForm = reactive({
  company_id: undefined as number | undefined,
  name: '',
  email: '',
  account_type: undefined as string | undefined,
  industry: undefined as string | undefined,
  settlement_type: undefined as string | undefined,
  settlement_cycle: undefined as string | undefined,
  is_key_customer: false,
  manager_id: null as number | null,
  sales_manager_id: null as number | null,
})

const customerFormRules = {
  company_id: [{ required: true, message: '请输入公司 ID', trigger: ['blur', 'change'] }],
  name: [{ required: true, message: '请输入客户名称', trigger: ['blur', 'change'] }],
  email: [{ type: 'email', message: '请输入有效的邮箱地址', trigger: ['blur', 'change'] }],
}

// 打开新建对话框
const openCreateModal = () => {
  isEditMode.value = false
  editingCustomerId.value = null
  Object.assign(customerForm, {
    company_id: undefined,
    name: '',
    email: '',
    account_type: undefined,
    industry: undefined,
    settlement_type: undefined,
    settlement_cycle: undefined,
    is_key_customer: false,
    manager_id: null,
    sales_manager_id: null,
  })
  customerModalVisible.value = true
}

// 打开编辑对话框
const openEditModal = (record: Customer) => {
  isEditMode.value = true
  editingCustomerId.value = record.id
  Object.assign(customerForm, {
    company_id: record.company_id,
    name: record.name,
    email: record.email || '',
    account_type: record.account_type,
    industry: record.industry,
    settlement_type: record.settlement_type,
    settlement_cycle: record.settlement_cycle,
    is_key_customer: record.is_key_customer,
    manager_id: record.manager_id || null,
    sales_manager_id: record.sales_manager_id || null,
  })
  customerModalVisible.value = true
}

const handleCustomerModalCancel = () => {
  customerModalVisible.value = false
  customerFormRef.value?.resetFields()
}

const handleCustomerSubmit = async () => {
  try {
    await customerFormRef.value?.validate()
  } catch {
    return false
  }

  customerModalLoading.value = true
  try {
    const data = {
      company_id: customerForm.company_id ?? 0,
      name: customerForm.name,
      email: customerForm.email || undefined,
      account_type: customerForm.account_type,
      industry: customerForm.industry,
      settlement_type: customerForm.settlement_type,
      settlement_cycle: customerForm.settlement_cycle,
      is_key_customer: customerForm.is_key_customer,
      manager_id: customerForm.manager_id || undefined,
      sales_manager_id: customerForm.sales_manager_id || undefined,
    }

    if (isEditMode.value && editingCustomerId.value) {
      await updateCustomer(editingCustomerId.value, data)
      Message.success('更新成功')
    } else {
      await createCustomer(data)
      Message.success('创建成功')
    }
    loadCustomers()
    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '操作失败')
    return false
  } finally {
    customerModalLoading.value = false
  }
}

// ========== 查看客户和画像 ==========
const viewCustomer = (id: number) => {
  router.push(`/customers/${id}`)
}

const viewProfile = (id: number) => {
  router.push(`/customers/${id}`)
}

// ========== 导入客户 ==========
const importModalVisible = ref(false)
const importLoading = ref(false)
const importFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

const openImportModal = () => {
  importFile.value = null
  importModalVisible.value = true
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleFileInputChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    validateAndSetFile(file)
  }
}

const handleFileDrop = (event: DragEvent) => {
  const file = event.dataTransfer?.files[0]
  if (file) {
    validateAndSetFile(file)
  }
}

const validateAndSetFile = (file: File) => {
  const allowedTypes = [
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
  ]
  const allowedExtensions = ['.xlsx', '.xls']
  const hasValidExtension = allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext))
  const hasValidType = allowedTypes.includes(file.type)

  if (!hasValidType && !hasValidExtension) {
    Message.error('仅支持上传 Excel 文件（.xlsx 或 .xls）')
    return
  }

  importFile.value = file
}

const removeFile = () => {
  importFile.value = null
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const downloadTemplate = async () => {
  try {
    const res = await downloadImportTemplate()
    const blob = res.data as Blob
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '客户导入模板.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    Message.success('模板下载成功')
  } catch (error: unknown) {
    Message.error((error as Error).message || '下载失败')
  }
}

const handleImportSubmit = async () => {
  if (!importFile.value) {
    Message.error('请选择要导入的文件')
    return false
  }

  importLoading.value = true
  try {
    const res = await importCustomers(importFile.value)
    const data = (res as { data: ImportResult }).data
    const { success_count, error_count, errors } = data

    if (error_count > 0) {
      // 有错误：展示详情
      const errorList = errors?.slice(0, 10).map((e: string) => `• ${e}`).join('\n') || ''
      const moreMsg = error_count > 10 ? `\n... 还有 ${error_count - 10} 条错误` : ''
      Message.warning({
        content: `导入完成：成功 ${success_count} 条，失败 ${error_count} 条\n${errorList}${moreMsg}`,
        duration: 8000,
      })
    } else {
      Message.success(`导入成功，共导入 ${success_count} 条客户数据`)
    }
    loadCustomers()
    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '导入失败')
    return false
  } finally {
    importLoading.value = false
  }
}

onMounted(() => {
  loadCustomers()
  loadManagers()
  loadCustomerTags()
  loadIndustryTypesData()
})
</script>

<style scoped>
.customer-list-page {
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
.filter-section .arco-input {
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

:deep(.arco-table) {
  font-size: 14px;
}

:deep(.arco-table th) {
  font-size: 13px;
  white-space: nowrap;
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

/* 重点客户名称单元格布局 */
.name-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}

.key-customer-badge {
  color: #ff4d4f;
  font-size: 14px;
  line-height: 1;
  flex-shrink: 0;
}

.name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.arco-form-item-required) .arco-form-item-label::before {
  content: '*';
  color: #ff4d4f;
  margin-right: 4px;
}

/* 导入弹框样式 */
.import-modal-content {
  padding: 4px 0;
}

.upload-area {
  border: 2px dashed var(--neutral-3);
  border-radius: 12px;
  padding: 40px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s ease;
  background: var(--neutral-1);
  margin-bottom: 20px;
}

.upload-area:hover {
  border-color: var(--primary-6);
  background: rgba(3, 105, 161, 0.04);
}

.upload-area:active {
  transform: scale(0.99);
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.upload-icon {
  color: var(--neutral-5);
  margin-bottom: 8px;
  transition: color 0.25s ease;
}

.upload-area:hover .upload-icon {
  color: var(--primary-6);
}

.upload-icon svg {
  width: 48px;
  height: 48px;
}

.upload-text-primary {
  font-size: 16px;
  font-weight: 500;
  color: var(--neutral-9);
  line-height: 1.5;
}

.upload-text-secondary {
  font-size: 13px;
  color: var(--neutral-6);
  line-height: 1.4;
}

.file-selected {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: white;
  border-radius: 10px;
  border: 1px solid var(--neutral-2);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.file-icon {
  color: var(--primary-6);
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
  text-align: left;
}

.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.file-size {
  font-size: 12px;
  color: var(--neutral-6);
}

.file-remove {
  color: var(--neutral-5);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.file-remove:hover {
  color: #ff4d4f;
  background: rgba(255, 77, 79, 0.08);
}

.file-input-hidden {
  display: none;
}

.import-tips {
  background: rgba(3, 105, 161, 0.04);
  border-radius: 8px;
  padding: 14px 16px;
  border-left: 3px solid var(--primary-6);
}

.tips-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--neutral-9);
  margin-bottom: 10px;
}

.tips-list {
  margin: 0;
  padding-left: 16px;
  list-style: disc;
}

.tips-list li {
  font-size: 12px;
  color: var(--neutral-7);
  line-height: 1.8;
}

.tips-list li:last-child {
  margin-bottom: 0;
}

/* 行业类型多选标签样式优化 */
.filter-section :deep(.arco-select-multiple .arco-tag) {
  max-width: calc(100% - 40px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: rgba(3, 105, 161, 0.08);
  color: var(--primary-6);
  border: none;
  border-radius: 4px;
  font-size: 12px;
  padding: 2px 8px;
}

/* 标签关闭按钮样式 */
.filter-section :deep(.arco-select-multiple .arco-tag .arco-icon-close) {
  color: var(--primary-6);
  opacity: 0.7;
  transition: opacity 0.2s;
}

.filter-section :deep(.arco-select-multiple .arco-tag .arco-icon-close:hover) {
  opacity: 1;
}

/* "+N" 提示样式 */
.filter-section :deep(.arco-select-multiple .arco-select-tag) {
  background: rgba(15, 23, 42, 0.06);
  color: var(--neutral-10);
  border: none;
  border-radius: 4px;
  font-size: 12px;
}
</style>
