<template>
  <div class="industry-types-page">
    <PageHeader eyebrow="System" title="行业类型"
      subtitle="管理系统行业类型字典">
      <template #actions>
        <a-button v-if="can('industry_types:manage')" type="primary" @click="handleCreate">新增行业类型</a-button>
      </template>
    </PageHeader>

    <div class="table-section">
      <a-table
        :columns="columns"
        :data="industryTypes"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #action="{ record }">
          <a-space>
            <a-button
              v-if="can('industry_types:manage')"
              type="text"
              size="small"
              @click="handleEdit(record)"
            >
              编辑
            </a-button>
            <a-popconfirm
              v-if="can('industry_types:manage')"
              content="确认删除该行业类型？删除后不会影响已关联的客户记录。"
              @ok="handleDelete(record.id)"
            >
              <a-button type="text" size="small" status="danger"> 删除 </a-button>
            </a-popconfirm>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无行业类型数据" description="点击「新增行业类型」添加第一个行业类型">
            <template #action>
              <a-button v-if="can('industry_types:manage')" type="primary" @click="handleCreate"
                >新增行业类型</a-button
              >
            </template>
          </EmptyState>
        </template>
        <template #created_at="{ record }">
          {{ formatDateTime(record.created_at) }}
        </template>
      </a-table>
    </div>

    <!-- 新增/编辑对话框 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEditMode ? '编辑行业类型' : '新增行业类型'"
      :confirm-loading="submitting"
      width="500px"
      @before-ok="handleSubmit"
      @cancel="handleModalCancel"
    >
      <a-form ref="formRef" :model="form" :rules="formRules" layout="vertical">
        <a-form-item field="name" label="行业类型名称">
          <a-input v-model="form.name" placeholder="请输入行业类型名称" />
        </a-form-item>
        <a-form-item field="sort_order" label="排序号">
          <a-input-number v-model="form.sort_order" placeholder="请输入排序号" :min="0" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import PageHeader from '@/components/PageHeader.vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import {
  getIndustryTypesList,
  createIndustryType,
  updateIndustryType,
  deleteIndustryType,
} from '@/api/industryTypes'
import type { IndustryType } from '@/types'
import EmptyState from '@/components/EmptyState.vue'
import { formatDateTime } from '@/utils/formatters'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// ========== 状态管理 ==========
const loading = ref(false)
const industryTypes = ref<IndustryType[]>([])

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

// 表格列定义
const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'right' as const },
  { title: '行业类型名称', dataIndex: 'name', width: 200 },
  { title: '排序号', dataIndex: 'sort_order', width: 100, align: 'center' as const },
  { title: '创建时间', slotName: 'created_at', width: 160 },
  { title: '操作', slotName: 'action', width: 150, fixed: 'right' as const },
]

// ========== 表单 ==========
const modalVisible = ref(false)
const isEditMode = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)

const form = reactive({
  name: '',
  sort_order: 0,
})

const formRules = {
  name: [{ required: true, message: '请输入行业类型名称' }],
  sort_order: [{ required: true, message: '请输入排序号' }],
}

// ========== 数据加载 ==========
const loadIndustryTypes = async () => {
  loading.value = true
  try {
    const res = await getIndustryTypesList()
    industryTypes.value = res.data?.data || res.data || []
    pagination.total = industryTypes.value.length
  } catch (error) {
    Message.error('加载行业类型失败')
    console.error('Failed to load industry types:', error)
  } finally {
    loading.value = false
  }
}

// ========== 事件处理 ==========
const handleCreate = () => {
  isEditMode.value = false
  editingId.value = null
  form.name = ''
  form.sort_order = 0
  modalVisible.value = true
}

const handleEdit = (record: IndustryType) => {
  isEditMode.value = true
  editingId.value = record.id
  form.name = record.name
  form.sort_order = record.sort_order
  modalVisible.value = true
}

const handleSubmit = async () => {
  try {
    submitting.value = true
    if (isEditMode.value && editingId.value !== null) {
      await updateIndustryType(editingId.value, {
        name: form.name,
        sort_order: form.sort_order,
      })
      Message.success('更新成功')
    } else {
      await createIndustryType({
        name: form.name,
        sort_order: form.sort_order,
      })
      Message.success('创建成功')
    }
    await loadIndustryTypes()
    return true
  } catch (error) {
    const msg = error instanceof Error ? error.message : '操作失败'
    Message.error(isEditMode.value ? `更新失败: ${msg}` : `创建失败: ${msg}`)
    console.error('Failed to save industry type:', error)
    return false
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await deleteIndustryType(id)
    Message.success('删除成功')
    await loadIndustryTypes()
  } catch (error) {
    Message.error('删除失败')
    console.error('Failed to delete industry type:', error)
  }
}

const handlePageChange = (page: number) => {
  pagination.current = page
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
}

const handleModalCancel = () => {
  formRef.value?.resetFields()
}

// ========== 生命周期 ==========
onMounted(() => {
  loadIndustryTypes()
})
</script>

<style scoped>
.industry-types-page {
  padding: 0; /* 移除 padding，由 Dashboard 统一提供 */
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 8px;
}

.header-subtitle {
  font-size: 13px;
  color: var(--muted);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.table-section {
  width: 100%;
  background: white;
  border-radius: 16px;
  border: 1px solid var(--soft);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

:deep(.arco-table) {
  font-size: 14px;
}

:deep(.arco-table th) {
  background: var(--bg);
  color: var(--muted);
  font-weight: 600;
}

:deep(.arco-table td) {
  color: #334155;
}

:deep(.arco-table tr:hover td) {
  background: var(--bg);
}
</style>
