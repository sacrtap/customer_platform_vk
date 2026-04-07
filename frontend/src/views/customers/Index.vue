<template>
  <div class="customer-list-page">
    <div class="page-header">
      <div class="header-title">
        <h1>客户管理</h1>
        <p class="header-subtitle">统一客户基础信息与画像数据管理</p>
      </div>
      <div class="header-actions">
        <a-button type="primary" @click="openCreateModal">
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
        <a-button @click="openImportModal">
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
        <a-button @click="handleExport">
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
      <a-form layout="inline" :model="filters">
        <a-form-item label="关键词">
          <a-input v-model="filters.keyword" placeholder="公司名称/公司 ID" style="width: 200px">
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
        <a-form-item label="账号类型">
          <a-select
            v-model="filters.account_type"
            placeholder="请选择"
            style="width: 150px"
            allow-clear
          >
            <a-option value="正式账号">正式账号</a-option>
            <a-option value="测试账号">测试账号</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="业务类型">
          <a-select
            v-model="filters.business_type"
            placeholder="请选择"
            style="width: 150px"
            allow-clear
          >
            <a-option value="A">A 类业务</a-option>
            <a-option value="B">B 类业务</a-option>
            <a-option value="C">C 类业务</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="客户等级">
          <a-select
            v-model="filters.customer_level"
            placeholder="请选择"
            style="width: 150px"
            allow-clear
          >
            <a-option value="KA">KA</a-option>
            <a-option value="SKA">SKA</a-option>
            <a-option value="普通">普通</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="重点客户">
          <a-select
            v-model="filters.is_key_customer"
            placeholder="请选择"
            style="width: 120px"
            allow-clear
          >
            <a-option :value="true">是</a-option>
            <a-option :value="false">否</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="handleSearch">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
            <a-button @click="showAdvancedFilter = !showAdvancedFilter">
              高级筛选
              <template #icon>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  fill="currentColor"
                  viewBox="0 0 16 16"
                  :style="{ transform: showAdvancedFilter ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }"
                >
                  <path
                    fill-rule="evenodd"
                    d="M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z"
                  />
                </svg>
              </template>
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>

      <!-- 高级筛选区域 -->
      <a-divider v-if="showAdvancedFilter" style="margin: 16px 0" />
      <a-form v-if="showAdvancedFilter" layout="inline" :model="advancedFilters">
        <a-form-item label="运营经理">
          <a-select
            v-model="advancedFilters.manager_id"
            placeholder="请选择运营经理"
            style="width: 150px"
            allow-clear
            :loading="managersLoading"
          >
            <a-option
              v-for="manager in managers"
              :key="manager.id"
              :value="manager.id"
            >
              {{ manager.real_name || manager.username }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="标签筛选">
          <a-select
            v-model="advancedFilters.tag_ids"
            placeholder="选择标签"
            style="width: 200px"
            multiple
            allow-clear
            :loading="tagsLoading"
          >
            <a-option
              v-for="tag in customerTags"
              :key="tag.id"
              :value="tag.id"
            >
              {{ tag.name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleAdvancedSearch">应用高级筛选</a-button>
        </a-form-item>
      </a-form>
    </div>

    <!-- 表格 -->
    <div class="table-section">
      <a-table
        :columns="columns"
        :data="customers"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="handlePageChange"
      >
        <template #action="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="viewCustomer(record.id)">查看</a-button>
            <a-button type="text" size="small" @click="openEditModal(record)">编辑</a-button>
            <a-button type="text" size="small" @click="viewProfile(record.id)">画像</a-button>
            <a-popconfirm content="确认删除？" @ok="() => handleDelete(record.id)">
              <a-button type="text" size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
        <template #empty>
          <EmptyState 
            title="暂无客户数据" 
            description="点击「新建客户」添加第一个客户"
          >
            <template #action>
              <a-button type="primary" @click="openCreateModal">新建客户</a-button>
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
      @ok="handleCustomerSubmit"
      @cancel="handleCustomerModalCancel"
    >
      <a-form
        ref="customerFormRef"
        :model="customerForm"
        :rules="customerFormRules"
        layout="vertical"
      >
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="company_id" label="公司 ID" required>
              <a-input
                v-model="customerForm.company_id"
                placeholder="请输入公司 ID"
                :disabled="isEditMode"
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
              <a-select v-model="customerForm.account_type" placeholder="请选择账号类型" allow-clear>
                <a-option value="正式账号">正式账号</a-option>
                <a-option value="测试账号">测试账号</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="business_type" label="业务类型">
              <a-select v-model="customerForm.business_type" placeholder="请选择业务类型" allow-clear>
                <a-option value="A">A 类业务</a-option>
                <a-option value="B">B 类业务</a-option>
                <a-option value="C">C 类业务</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="customer_level" label="客户等级">
              <a-select v-model="customerForm.customer_level" placeholder="请选择客户等级" allow-clear>
                <a-option value="KA">KA</a-option>
                <a-option value="SKA">SKA</a-option>
                <a-option value="普通">普通</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="settlement_type" label="结算方式">
              <a-select v-model="customerForm.settlement_type" placeholder="请选择结算方式" allow-clear>
                <a-option value="prepaid">预付费</a-option>
                <a-option value="postpaid">后付费</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="settlement_cycle" label="结算周期">
              <a-select v-model="customerForm.settlement_cycle" placeholder="请选择结算周期" allow-clear>
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

        <a-form-item field="manager" label="运营经理">
          <a-input v-model="customerForm.manager" placeholder="请输入运营经理姓名" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 导入对话框 -->
    <a-modal
      v-model:visible="importModalVisible"
      title="导入客户"
      :confirm-loading="importLoading"
      width="500px"
      @ok="handleImportSubmit"
      @cancel="importModalVisible = false"
    >
      <a-alert type="info" style="margin-bottom: 16px">
        请下载模板文件，填写后上传 Excel 文件进行导入
        <template #action>
          <a-button type="text" size="small" @click="downloadTemplate">下载模板</a-button>
        </template>
      </a-alert>
      <a-form layout="vertical">
        <a-form-item label="上传 Excel 文件" required>
          <a-upload
            :file-list="importFileList"
            :show-file-list="true"
            :on-change="handleImportFileChange"
            :auto-upload="false"
          >
            <template #upload-button>
              <div class="arco-upload-list-item">
                <div class="arco-upload-list-item-custom-icon">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    fill="currentColor"
                    viewBox="0 0 16 16"
                  >
                    <path
                      d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"
                    />
                  </svg>
                </div>
                <div class="arco-upload-list-item-custom-text">
                  <span>点击或拖拽文件到此处</span>
                </div>
              </div>
            </template>
          </a-upload>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import {
  getCustomers,
  deleteCustomer,
  exportCustomers,
  createCustomer,
  updateCustomer,
  importCustomers,
  downloadImportTemplate,
} from '@/api/customers'
import { getTags } from '@/api/tags'
import { getManagers } from '@/api/users'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()

const filters = reactive({
  keyword: '',
  account_type: '',
  business_type: '',
  customer_level: '',
  is_key_customer: null as boolean | null,
})

const showAdvancedFilter = ref(false)
const advancedFilters = reactive({
  manager_id: null as number | null,
  tag_ids: [] as number[],
})

const managersLoading = ref(false)
const managers = ref<any[]>([])
const tagsLoading = ref(false)
const customerTags = ref<any[]>([])

const loading = ref(false)
const customers = ref<any[]>([])

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const columns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 120, ellipsis: true, tooltip: true },
  { title: '客户名称', dataIndex: 'name', width: 200, ellipsis: true, tooltip: true },
  { title: '业务类型', dataIndex: 'business_type', width: 100 },
  { title: '客户等级', dataIndex: 'customer_level', width: 100 },
  { title: '结算方式', dataIndex: 'settlement_type', width: 100 },
  { title: '运营经理', dataIndex: 'manager', width: 120, ellipsis: true, tooltip: true },
  { title: '重点客户', dataIndex: 'is_key_customer', width: 90 },
  { title: '创建时间', dataIndex: 'created_at', width: 180 },
  { title: '操作', slotName: 'action', width: 280, fixed: 'right' as const },
]

// 加载客户列表
const loadCustomers = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.account_type) params.account_type = filters.account_type
    if (filters.business_type) params.business_type = filters.business_type
    if (filters.customer_level) params.customer_level = filters.customer_level
    if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
    if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id

    const res = await getCustomers(params)
    customers.value = res.data.list || []
    pagination.total = res.data.total || 0
    pagination.current = res.data.page || 1
  } catch (error: any) {
    Message.error(error.message || '加载失败')
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
  filters.keyword = ''
  filters.account_type = ''
  filters.business_type = ''
  filters.customer_level = ''
  filters.is_key_customer = null
  advancedFilters.manager_id = null
  advancedFilters.tag_ids = []
  pagination.current = 1
  loadCustomers()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
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
      } catch (error: any) {
        Message.error(error.message || '删除失败')
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
  } catch (error: any) {
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
  } catch (error: any) {
    console.error('加载标签失败:', error)
  } finally {
    tagsLoading.value = false
  }
}

// 导出客户
const handleExport = async () => {
  try {
    const params: any = {}
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.account_type) params.account_type = filters.account_type
    if (filters.business_type) params.business_type = filters.business_type
    if (filters.customer_level) params.customer_level = filters.customer_level
    if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
    if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id

    const res = await exportCustomers(params)
    
    // 处理文件下载
    const blob = new Blob([res as unknown as Blob], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `customers_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    Message.success('导出成功')
  } catch (error: any) {
    Message.error(error.message || '导出失败')
  }
}

// ========== 新建/编辑客户 ==========
const customerModalVisible = ref(false)
const customerModalLoading = ref(false)
const customerFormRef = ref<FormInstance>()
const isEditMode = ref(false)
const editingCustomerId = ref<number | null>(null)

const customerForm = reactive({
  company_id: '',
  name: '',
  email: '',
  account_type: undefined as string | undefined,
  business_type: undefined as string | undefined,
  customer_level: undefined as string | undefined,
  settlement_type: undefined as string | undefined,
  settlement_cycle: undefined as string | undefined,
  is_key_customer: false,
  manager: '',
})

const customerFormRules = {
  company_id: [{ required: true, message: '请输入公司 ID' }],
  name: [{ required: true, message: '请输入客户名称' }],
  email: [{ type: 'email', message: '请输入有效的邮箱地址' }],
}

// 打开新建对话框
const openCreateModal = () => {
  isEditMode.value = false
  editingCustomerId.value = null
  Object.assign(customerForm, {
    company_id: '',
    name: '',
    email: '',
    account_type: undefined,
    business_type: undefined,
    customer_level: undefined,
    settlement_type: undefined,
    settlement_cycle: undefined,
    is_key_customer: false,
    manager: '',
  })
  customerModalVisible.value = true
}

// 打开编辑对话框
const openEditModal = (record: any) => {
  isEditMode.value = true
  editingCustomerId.value = record.id
  Object.assign(customerForm, {
    company_id: record.company_id,
    name: record.name,
    email: record.email || '',
    account_type: record.account_type,
    business_type: record.business_type,
    customer_level: record.customer_level,
    settlement_type: record.settlement_type,
    settlement_cycle: record.settlement_cycle,
    is_key_customer: record.is_key_customer,
    manager: record.manager || '',
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
    return
  }

  customerModalLoading.value = true
  try {
    const data: any = {
      company_id: customerForm.company_id,
      name: customerForm.name,
      email: customerForm.email || undefined,
      account_type: customerForm.account_type,
      business_type: customerForm.business_type,
      customer_level: customerForm.customer_level,
      settlement_type: customerForm.settlement_type,
      settlement_cycle: customerForm.settlement_cycle,
      is_key_customer: customerForm.is_key_customer,
      manager: customerForm.manager || undefined,
    }

    if (isEditMode.value && editingCustomerId.value) {
      await updateCustomer(editingCustomerId.value, data)
      Message.success('更新成功')
    } else {
      await createCustomer(data)
      Message.success('创建成功')
    }
    customerModalVisible.value = false
    loadCustomers()
  } catch (error: any) {
    Message.error(error.message || '操作失败')
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
const importFileList = ref<any[]>([])

const openImportModal = () => {
  importFileList.value = []
  importModalVisible.value = true
}

const handleImportFileChange = (file: any) => {
  importFileList.value = [file]
}

const downloadTemplate = async () => {
  try {
    const res = await downloadImportTemplate()
    const blob = new Blob([res as unknown as Blob], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '客户导入模板.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    Message.success('模板下载成功')
  } catch (error: any) {
    Message.error(error.message || '下载失败')
  }
}

const handleImportSubmit = async () => {
  if (importFileList.value.length === 0) {
    Message.error('请选择要导入的文件')
    return
  }

  importLoading.value = true
  try {
    const file = importFileList.value[0].originFile
    await importCustomers(file)
    Message.success('导入成功')
    importModalVisible.value = false
    loadCustomers()
  } catch (error: any) {
    Message.error(error.message || '导入失败')
  } finally {
    importLoading.value = false
  }
}

onMounted(() => {
  loadCustomers()
  loadManagers()
  loadCustomerTags()
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
