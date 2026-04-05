<template>
  <div class="customer-list">
    <a-card>
      <template #title>
        <a-space>
          <span>客户管理</span>
          <a-button type="primary" @click="showCreateModal">
            <template #icon><icon-plus /></template>
            新建客户
          </a-button>
          <a-button @click="showImportModal">
            <template #icon><icon-upload /></template>
            导入客户
          </a-button>
          <a-button @click="handleExport">
            <template #icon><icon-download /></template>
            导出
          </a-button>
        </a-space>
      </template>

      <!-- 筛选区域 -->
      <a-form :model="filters" layout="inline" class="filter-form">
        <a-form-item label="关键词">
          <a-input
            v-model="filters.keyword"
            placeholder="公司名称/公司 ID"
            style="width: 200px"
            @press-enter="handleSearch"
          >
            <template #prefix><icon-search /></template>
          </a-input>
        </a-form-item>
        <a-form-item label="账号类型">
          <a-select v-model="filters.account_type" placeholder="请选择" style="width: 150px" allow-clear>
            <a-option value="test">测试账号</a-option>
            <a-option value="formal">正式账号</a-option>
          </a-select>
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
        <a-form-item label="结算方式">
          <a-select v-model="filters.settlement_type" placeholder="请选择" style="width: 120px" allow-clear>
            <a-option value="prepaid">预付费</a-option>
            <a-option value="postpaid">后付费</a-option>
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

      <!-- 表格 -->
      <a-table
        :columns="columns"
        :data="data"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
      >
        <template #name="{ record }">
          <a-space>
            <a-avatar v-if="record.is_key_customer" :size="24" style="background-color: rgb(var(--primary-6))">
              <icon-star />
            </a-avatar>
            <a-avatar v-else :size="24">{{ record.name.charAt(0) }}</a-avatar>
            <span>{{ record.name }}</span>
          </a-space>
        </template>
        <template #is_key_customer="{ record }">
          <a-tag :color="record.is_key_customer ? 'orangered' : 'gray'">
            {{ record.is_key_customer ? '重点' : '普通' }}
          </a-tag>
        </template>
        <template #settlement_type="{ record }">
          <a-tag :color="record.settlement_type === 'prepaid' ? 'green' : 'arcoblue'">
            {{ record.settlement_type === 'prepaid' ? '预付费' : '后付费' }}
          </a-tag>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="viewDetail(record)">详情</a-button>
            <a-button type="text" size="small" @click="showEditModal(record)">编辑</a-button>
            <a-button type="text" size="small" status="danger" @click="handleDelete(record)">删除</a-button>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <!-- 创建/编辑客户弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :confirm-loading="modalLoading"
      width="600px"
      @ok="handleSubmit"
    >
      <a-form :model="formData" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item
              label="公司 ID"
              :rules="[{ required: true, message: '请输入公司 ID' }]"
            >
              <a-input
                v-model="formData.company_id"
                :disabled="isEdit"
                placeholder="请输入公司 ID"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item
              label="客户名称"
              :rules="[{ required: true, message: '请输入客户名称' }]"
            >
              <a-input v-model="formData.name" placeholder="请输入客户名称" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="账号类型">
              <a-select v-model="formData.account_type" placeholder="请选择">
                <a-option value="test">测试账号</a-option>
                <a-option value="formal">正式账号</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="业务类型">
              <a-select v-model="formData.business_type" placeholder="请选择">
                <a-option value="A">A 类业务</a-option>
                <a-option value="B">B 类业务</a-option>
                <a-option value="C">C 类业务</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="客户等级">
              <a-select v-model="formData.customer_level" placeholder="请选择">
                <a-option value="KA">KA</a-option>
                <a-option value="SKA">SKA</a-option>
                <a-option value="普通">普通</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="结算方式">
              <a-select v-model="formData.settlement_type" placeholder="请选择">
                <a-option value="prepaid">预付费</a-option>
                <a-option value="postpaid">后付费</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="结算周期">
              <a-select v-model="formData.settlement_cycle" placeholder="请选择">
                <a-option value="monthly">月度</a-option>
                <a-option value="quarterly">季度</a-option>
                <a-option value="yearly">年度</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="重点客户">
              <a-switch v-model="formData.is_key_customer" checked-children="是" unchecked-children="否" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="邮箱">
          <a-input v-model="formData.email" placeholder="请输入邮箱" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 导入弹窗 -->
    <a-modal v-model:visible="importModalVisible" title="导入客户" :confirm-loading="importLoading" @ok="handleImport">
      <a-upload :auto-upload="false" :show-file-list="false" :before-upload="handleBeforeUpload">
        <template #upload-area>
          <a-upload-dragger :multiple="false">
            <a-space direction="vertical" style="padding: 20px">
              <icon-upload style="font-size: 48px; color: var(--color-text-4)" />
              <a-typography-paragraph style="margin: 0">
                点击或拖拽文件到此处上传
              </a-typography-paragraph>
              <a-typography-text type="secondary" style="font-size: 12px">
                仅支持 .xlsx 格式文件
              </a-typography-text>
            </a-space>
          </a-upload-dragger>
        </template>
      </a-upload>
      <a-alert v-if="importResult" :type="importResult.error_count > 0 ? 'warning' : 'success'" style="margin-top: 16px">
        导入完成：成功 {{ importResult.success_count }} 条
        <span v-if="importResult.error_count > 0">
          ，失败 {{ importResult.error_count }} 条
          <a-divider direction="vertical" />
          <a-typography-text type="secondary">
            {{ importResult.errors?.slice(0, 3).join('; ') }}
          </a-typography-text>
        </span>
      </a-alert>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import {
  IconPlus,
  IconUpload,
  IconDownload,
  IconSearch,
  IconStar,
} from '@arco-design/web-vue/es/icon'
import * as customerApi from '@/api/customers'
import { useRouter } from 'vue-router'

const router = useRouter()

interface Customer {
  id: number
  company_id: string
  name: string
  account_type?: string
  business_type?: string
  customer_level?: string
  price_policy?: string
  settlement_cycle?: string
  settlement_type?: string
  is_key_customer: boolean
  email?: string
}

const columns = [
  { title: '客户名称', dataIndex: 'name', slotName: 'name', width: 200 },
  { title: '公司 ID', dataIndex: 'company_id', width: 120 },
  { title: '账号类型', dataIndex: 'account_type', width: 100 },
  { title: '业务类型', dataIndex: 'business_type', width: 100 },
  { title: '客户等级', dataIndex: 'customer_level', width: 100 },
  { title: '结算方式', dataIndex: 'settlement_type', slotName: 'settlement_type', width: 100 },
  { title: '重点客户', dataIndex: 'is_key_customer', slotName: 'is_key_customer', width: 90 },
  { title: '邮箱', dataIndex: 'email', width: 180 },
  { title: '操作', slotName: 'action', width: 200, fixed: 'right' },
]

const data = ref<Customer[]>([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

interface CustomerFilters {
  keyword?: string
  company_id?: string
  name?: string
  account_type?: string
  business_type?: string
  customer_level?: string
  settlement_type?: string
  is_key_customer?: boolean
  manager_id?: number
  [key: string]: string | number | boolean | undefined
}

const filters = reactive<CustomerFilters>({
  keyword: '',
  account_type: undefined as string | undefined,
  business_type: undefined as string | undefined,
  customer_level: undefined as string | undefined,
  settlement_type: undefined as string | undefined,
  is_key_customer: undefined as boolean | undefined,
})

const modalVisible = ref(false)
const modalTitle = ref('新建客户')
const modalLoading = ref(false)
const isEdit = ref(false)

const formData = reactive({
  id: null as number | null,
  company_id: '',
  name: '',
  account_type: undefined as string | undefined,
  business_type: undefined as string | undefined,
  customer_level: undefined as string | undefined,
  settlement_cycle: undefined as string | undefined,
  settlement_type: undefined as string | undefined,
  is_key_customer: false,
  email: '',
})

const importModalVisible = ref(false)
const importLoading = ref(false)
const importFile = ref<File | null>(null)
const importResult = ref<{
  success_count: number
  error_count: number
  errors?: string[]
} | null>(null)

const fetchData = async () => {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    Object.keys(filters).forEach((key) => {
      const value = filters[key]
      if (value !== undefined && value !== '') {
        params[key] = value
      }
    })
    const res = await customerApi.getCustomers(params)
    data.value = res.data.list
    pagination.total = res.data.total
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '加载失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchData()
}

const handleReset = () => {
  Object.keys(filters).forEach((key) => {
    ;(filters as Record<string, unknown>)[key] = undefined
  })
  pagination.current = 1
  fetchData()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchData()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchData()
}

const showCreateModal = () => {
  isEdit.value = false
  modalTitle.value = '新建客户'
  Object.assign(formData, {
    id: null,
    company_id: '',
    name: '',
    account_type: undefined,
    business_type: undefined,
    customer_level: undefined,
    settlement_cycle: undefined,
    settlement_type: undefined,
    is_key_customer: false,
    email: '',
  })
  modalVisible.value = true
}

const showEditModal = (record: Customer) => {
  isEdit.value = true
  modalTitle.value = '编辑客户'
  Object.assign(formData, {
    id: record.id,
    company_id: record.company_id,
    name: record.name,
    account_type: record.account_type,
    business_type: record.business_type,
    customer_level: record.customer_level,
    settlement_cycle: record.settlement_cycle,
    settlement_type: record.settlement_type,
    is_key_customer: record.is_key_customer,
    email: record.email,
  })
  modalVisible.value = true
}

const handleSubmit = async () => {
  modalLoading.value = true
  try {
    if (isEdit.value && formData.id) {
      await customerApi.updateCustomer(formData.id, {
        name: formData.name,
        account_type: formData.account_type,
        business_type: formData.business_type,
        customer_level: formData.customer_level,
        settlement_cycle: formData.settlement_cycle,
        settlement_type: formData.settlement_type,
        is_key_customer: formData.is_key_customer,
        email: formData.email,
      })
      Message.success('更新成功')
    } else {
      await customerApi.createCustomer({
        company_id: formData.company_id,
        name: formData.name,
        account_type: formData.account_type,
        business_type: formData.business_type,
        customer_level: formData.customer_level,
        settlement_cycle: formData.settlement_cycle,
        settlement_type: formData.settlement_type,
        is_key_customer: formData.is_key_customer,
        email: formData.email,
      })
      Message.success('创建成功')
    }
    modalVisible.value = false
    fetchData()
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

const handleDelete = (record: Customer) => {
  Modal.warning({
    title: '确认删除',
    content: `确定要删除客户 ${record.name} 吗？`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        await customerApi.deleteCustomer(record.id)
        Message.success('删除成功')
        fetchData()
      } catch (err: unknown) {
        Message.error(((err as Error)?.message) || '删除失败')
      }
    },
  })
}

const viewDetail = (record: Customer) => {
  router.push(`/customers/${record.id}`)
}

const showImportModal = () => {
  importModalVisible.value = true
  importResult.value = null
  importFile.value = null
}

const handleBeforeUpload = (file: File) => {
  if (!file.name.endsWith('.xlsx')) {
    Message.error('仅支持 .xlsx 格式文件')
    return false
  }
  importFile.value = file
  return true
}

const handleImport = async () => {
  if (!importFile.value) {
    Message.warning('请选择文件')
    return
  }
  importLoading.value = true
  try {
    const res = await customerApi.importCustomers(importFile.value)
    importResult.value = res.data
    if (res.data.error_count === 0) {
      Message.success('导入成功')
      importModalVisible.value = false
      fetchData()
    }
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '导入失败')
  } finally {
    importLoading.value = false
  }
}

const handleExport = async () => {
  try {
    const params: Record<string, unknown> = {}
    Object.keys(filters).forEach((key) => {
      const value = filters[key]
      if (value !== undefined && value !== '') {
        params[key] = value
      }
    })
    const res = await customerApi.exportCustomers(params)
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const timestamp = new Date().toISOString().replace(/[:-]/g, '').slice(0, 14)
    link.download = `customers_${timestamp}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    Message.success('导出成功')
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '导出失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.customer-list {
  padding: 20px;
}

.filter-form {
  margin-bottom: 16px;
}
</style>
