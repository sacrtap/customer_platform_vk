<template>
  <div class="package-plans-page">
    <!-- PageHeader -->
    <PageHeader
      eyebrow="Billing"
      title="包年套餐"
      subtitle="管理包年结算套餐明细，支持限量与不限量配置"
    >
      <template #actions>
        <button v-if="can('billing:edit')" class="btn primary" @click="showCreateModal">
          新建套餐
        </button>
      </template>
    </PageHeader>

    <!-- 筛选 + 表格 在同一卡片内 -->
    <div class="card pad main-card">
      <!-- 筛选器 -->
      <div class="filters-container">
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
              placeholder="搜索套餐名称 / 类型"
              @keydown.enter="handleSearch"
            />
          </div>
          <FilterDropdown
            v-model="filters.status"
            label="状态"
            :options="statusOptions"
            @apply="handleSearch"
          />
          <FilterDropdown
            v-model="filters.is_unlimited"
            label="限量类型"
            :options="unlimitedOptions"
            @apply="handleSearch"
          />
          <button type="button" class="btn primary" @click="handleSearch">筛选</button>
          <button type="button" class="btn" @click="handleReset">重置</button>
        </div>
      </div>

      <!-- 表格 -->
      <div class="table-section">
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th style="width: 200px">套餐名称</th>
                <th style="width: 120px">套餐类型</th>
                <th style="width: 120px">限量类型</th>
                <th style="width: 120px">限量数量</th>
                <th style="width: 140px">基础费用（年）</th>
                <th style="width: 140px">超额单价</th>
                <th style="width: 100px">状态</th>
                <th style="width: 150px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in data" :key="record.id">
                <!-- 套餐名称 -->
                <td>
                  <span class="cust-name">{{ record.name }}</span>
                </td>
                <!-- 套餐类型 -->
                <td>
                  <span class="tag violet">{{ record.package_type }}</span>
                </td>
                <!-- 限量类型 -->
                <td>
                  <span v-if="record.is_unlimited" class="tag green">不限量</span>
                  <span v-else class="tag amber">限量</span>
                </td>
                <!-- 限量数量 -->
                <td>
                  <span v-if="record.is_unlimited" class="subtle">-</span>
                  <span v-else-if="record.limit_count != null" class="amount">{{
                    record.limit_count.toLocaleString()
                  }}</span>
                  <span v-else class="subtle">未设置</span>
                </td>
                <!-- 基础费用 -->
                <td>
                  <span class="amount">¥{{ record.base_fee.toFixed(2) }}</span>
                </td>
                <!-- 超额单价 -->
                <td>
                  <span v-if="record.is_unlimited" class="subtle">-</span>
                  <span v-else-if="record.over_limit_unit_price != null" class="amount"
                    >¥{{ record.over_limit_unit_price.toFixed(2) }}</span
                  >
                  <span v-else class="subtle">自动</span>
                </td>
                <!-- 状态 -->
                <td>
                  <span v-if="record.status === 'active'" class="tag green">启用</span>
                  <span v-else class="tag gray">停用</span>
                </td>
                <!-- 操作 -->
                <td style="white-space: nowrap">
                  <button
                    v-if="can('billing:edit')"
                    class="btn"
                    style="padding: 4px 10px; font-size: 12px"
                    @click="showEditModal(record)"
                  >
                    编辑
                  </button>
                  <button
                    v-if="can('billing:delete')"
                    class="btn btn-danger"
                    style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
                    @click="handleDelete(record)"
                  >
                    删除
                  </button>
                </td>
              </tr>
              <tr v-if="data.length === 0 && !loading">
                <td :colspan="8" class="empty-state">暂无包年套餐数据</td>
              </tr>
              <tr v-if="loading">
                <td :colspan="8" class="loading-state">加载中...</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分页 -->
        <Pagination
          :current="pagination.current"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @page-change="onPageChange"
          @page-size-change="onPageSizeChange"
        />
      </div>
    </div>

    <!-- 创建/编辑套餐弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :confirm-loading="modalLoading"
      width="600px"
      @before-ok="handleSubmit"
    >
      <a-form :model="formData" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="套餐名称" :rules="[{ required: true, message: '请输入套餐名称' }]">
              <a-input v-model="formData.name" placeholder="如：A 套餐" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item
              label="套餐类型标识"
              :rules="[{ required: true, message: '请输入套餐类型标识' }]"
              extra="套餐类型标识创建后不可修改"
            >
              <a-input v-model="formData.package_type" placeholder="如：A" :disabled="isEdit" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="状态">
              <a-select v-model="formData.status">
                <a-option value="active">启用</a-option>
                <a-option value="inactive">停用</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item
          label="基础费用（年费）"
          :rules="[{ required: true, message: '请输入基础费用' }]"
        >
          <a-input-number
            v-model="formData.base_fee"
            placeholder="请输入年费"
            :min="0"
            :precision="2"
            style="width: 100%"
          >
            <template #prefix>¥</template>
          </a-input-number>
        </a-form-item>

        <!-- 限量 / 不限量 -->
        <a-form-item label="限量配置" :rules="[{ required: true, message: '请选择限量类型' }]">
          <a-radio-group v-model="formData.is_unlimited" @change="onUnlimitedChange">
            <a-radio :value="false">限量</a-radio>
            <a-radio :value="true">不限量</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item
          v-if="!formData.is_unlimited"
          label="限量数量"
          :rules="[{ required: true, message: '请输入限量数量' }]"
        >
          <a-input-number
            v-model="formData.limit_count"
            placeholder="请输入具体数量"
            :min="1"
            :precision="0"
            style="width: 100%"
          />
        </a-form-item>

        <a-form-item
          v-if="!formData.is_unlimited"
          label="超额单价"
          extra="限量套餐超出限量数量后的每单位用量价格，留空则默认为 基础费用 ÷ 限量数量"
        >
          <a-input-number
            v-model="formData.over_limit_unit_price"
            placeholder="留空则自动计算"
            :min="0"
            :precision="2"
            style="width: 100%"
          >
            <template #prefix>¥</template>
          </a-input-number>
        </a-form-item>

        <a-form-item label="描述">
          <a-textarea
            v-model="formData.description"
            placeholder="可选：套餐描述"
            :max-length="500"
            show-word-limit
            :auto-size="{ minRows: 2, maxRows: 4 }"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import * as billingApi from '@/api/billing'
import PageHeader from '@/components/PageHeader.vue'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import Pagination from '@/components/ui/Pagination.vue'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

interface PackagePlan {
  id: number
  name: string
  package_type: string
  device_type?: string
  layer_type?: string
  is_unlimited: boolean
  limit_count?: number | null
  base_fee: number
  over_limit_unit_price?: number | null
  description?: string
  status: 'active' | 'inactive'
  created_at?: string
  updated_at?: string
}

// 筛选选项
const statusOptions = [
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' },
]

const unlimitedOptions = [
  { label: '限量', value: 'false' },
  { label: '不限量', value: 'true' },
]

const data = ref<PackagePlan[]>([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
})

const filters = reactive({
  keyword: '',
  status: '',
  is_unlimited: '',
})

const modalVisible = ref(false)
const modalTitle = ref('新建套餐')
const modalLoading = ref(false)
const isEdit = ref(false)

const formData = reactive({
  id: null as number | null,
  name: '',
  package_type: '',
  is_unlimited: false,
  limit_count: undefined as number | undefined,
  base_fee: undefined as number | undefined,
  over_limit_unit_price: undefined as number | undefined,
  description: '',
  status: 'active' as 'active' | 'inactive',
})

// --- 分页计算 ---
const onPageChange = (page: number) => {
  pagination.current = page
  fetchData()
}

const onPageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
  fetchData()
}

const handleReset = () => {
  filters.keyword = ''
  filters.status = ''
  filters.is_unlimited = ''
  pagination.current = 1
  fetchData()
}

// --- 数据请求 ---
const fetchData = async () => {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.status) params.status = filters.status
    if (filters.is_unlimited) params.is_unlimited = filters.is_unlimited

    const res = await billingApi.getPackagePlans(params)
    data.value = res.data.list || []
    pagination.total = res.data.total || data.value.length
    pagination.pageSize = res.data.page_size || pagination.pageSize
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchData()
}

const showCreateModal = () => {
  isEdit.value = false
  modalTitle.value = '新建套餐'
  Object.assign(formData, {
    id: null,
    name: '',
    package_type: '',
    is_unlimited: false,
    limit_count: undefined,
    base_fee: undefined,
    over_limit_unit_price: undefined,
    description: '',
    status: 'active',
  })
  modalVisible.value = true
}

const showEditModal = (record: PackagePlan) => {
  isEdit.value = true
  modalTitle.value = '编辑套餐'
  Object.assign(formData, {
    id: record.id,
    name: record.name,
    package_type: record.package_type,
    is_unlimited: record.is_unlimited,
    limit_count: record.limit_count ?? undefined,
    base_fee: record.base_fee,
    over_limit_unit_price: record.over_limit_unit_price ?? undefined,
    description: record.description || '',
    status: record.status,
  })
  modalVisible.value = true
}

// 切换限量/不限量时清空 limit_count 和 over_limit_unit_price
const onUnlimitedChange = (value: string | number | boolean) => {
  if (value === true) {
    formData.limit_count = undefined
    formData.over_limit_unit_price = undefined
  }
}

const handleSubmit = async () => {
  if (!formData.name.trim()) {
    Message.warning('请输入套餐名称')
    return false
  }
  if (!formData.package_type.trim()) {
    Message.warning('请输入套餐类型标识')
    return false
  }
  if (formData.base_fee == null) {
    Message.warning('请输入基础费用')
    return false
  }

  // 限量校验
  if (!formData.is_unlimited) {
    if (formData.limit_count == null || formData.limit_count <= 0) {
      Message.warning('限量套餐必须填写具体数量（大于 0）')
      return false
    }
  }

  modalLoading.value = true
  try {
    const submitData: Partial<PackagePlan> = {
      name: formData.name.trim(),
      package_type: formData.package_type.trim(),
      is_unlimited: formData.is_unlimited,
      limit_count: formData.is_unlimited ? null : formData.limit_count,
      base_fee: formData.base_fee,
      over_limit_unit_price: formData.is_unlimited ? null : formData.over_limit_unit_price,
      description: formData.description || undefined,
      status: formData.status,
    }

    if (isEdit.value && formData.id) {
      await billingApi.updatePackagePlan(formData.id, submitData)
      Message.success('更新成功')
    } else {
      await billingApi.createPackagePlan(submitData)
      Message.success('创建成功')
    }
    fetchData()
    return true
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '操作失败')
    return false
  } finally {
    modalLoading.value = false
  }
}

const handleDelete = (record: PackagePlan) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除套餐「${record.name}」吗？此操作不可恢复。`,
    onOk: async () => {
      try {
        await billingApi.deletePackagePlan(record.id)
        Message.success('删除成功')
        fetchData()
      } catch (err: unknown) {
        Message.error((err as Error)?.message || '删除失败')
      }
    },
  })
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.package-plans-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 1440px;
  margin: 0 auto;
}

/* 覆盖 PageHeader 的 margin-bottom，使用 gap 控制间距 */
.package-plans-page :deep(.page-header) {
  margin-bottom: 0;
}

/* 按钮样式 */
.btn {
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  border-radius: 12px;
  padding: 9px 12px;
  cursor: pointer;
  font-weight: 700;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}
.btn:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}
.btn.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}
.btn.primary:hover {
  background: #1e40af;
}
.btn.btn-danger {
  color: var(--red);
  border-color: #fecaca;
}
.btn.btn-danger:hover {
  background: #fef2f2;
  border-color: #fca5a5;
}

/* 搜索输入框 */
.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  padding: 9px 12px;
  min-width: 200px;
  flex: 1;
  max-width: 300px;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}
.search-input-wrap:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1);
}
.search-input-wrap svg {
  flex-shrink: 0;
  color: var(--muted);
}
.search-input-wrap input {
  border: 0;
  outline: 0;
  width: 100%;
  font: inherit;
  font-size: 13px;
  color: var(--ink);
  background: transparent;
}
.search-input-wrap input::placeholder {
  color: var(--muted);
}

@media (max-width: 1100px) {
  .search-input-wrap {
    width: 100%;
    max-width: none;
  }
}

/* 筛选器 */
.filters-container {
  margin-bottom: 12px;
}
.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

/* 表格容器 */
.table-section {
  display: flex;
  flex-direction: column;
}
.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 15px;
}

/* 表格 */
.table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  table-layout: auto;
}
.table th,
.table td {
  padding: 10px 10px;
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  white-space: nowrap;
}
.table th {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
}
.table tbody tr {
  transition: background 0.15s;
}
.table tbody tr:hover td {
  background: #f8fbff;
}

/* 客户名称 */
.cust-name {
  font-weight: 600;
  color: var(--ink);
}

/* 金额 */
.amount {
  font-weight: 500;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

/* 空状态 / 加载状态 */
.empty-state,
.loading-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--muted);
  font-size: 14px;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #edf2f7;
}

@media (max-width: 1100px) {
  .filters {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
