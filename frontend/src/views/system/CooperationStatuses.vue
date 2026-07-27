<template>
  <div class="cooperation-statuses-page">
    <PageHeader eyebrow="System" title="合作状态" subtitle="管理系统合作状态字典">
      <template #actions>
        <a-button v-if="can('cooperation_statuses:manage')" type="primary" @click="handleCreate"
          >新增合作状态</a-button
        >
      </template>
    </PageHeader>

    <div class="table-section">
      <a-table
        :columns="columns"
        :data="cooperationStatuses"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #action="{ record }">
          <a-space>
            <a-button
              v-if="can('cooperation_statuses:manage')"
              type="text"
              size="small"
              @click="handleEdit(record)"
            >
              编辑
            </a-button>
            <a-popconfirm
              v-if="can('cooperation_statuses:manage')"
              content="确认删除该合作状态？删除后不会影响已关联的客户记录。"
              @ok="handleDelete(record.id)"
            >
              <a-button type="text" size="small" status="danger"> 删除 </a-button>
            </a-popconfirm>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无合作状态数据" description="点击「新增合作状态」添加第一个合作状态">
            <template #action>
              <a-button
                v-if="can('cooperation_statuses:manage')"
                type="primary"
                @click="handleCreate"
                >新增合作状态</a-button
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
      :title="isEditMode ? '编辑合作状态' : '新增合作状态'"
      :confirm-loading="submitting"
      width="500px"
      @before-ok="handleSubmit"
      @cancel="handleModalCancel"
    >
      <a-form ref="formRef" :model="form" :rules="formRules" layout="vertical">
        <a-form-item field="name" label="合作状态名称">
          <a-input v-model="form.name" placeholder="请输入展示名称，如「合作中」" />
        </a-form-item>
        <a-form-item field="value" label="存储值">
          <a-input v-model="form.value" placeholder="请输入存储值，如「active」" />
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
  getCooperationStatusesList,
  createCooperationStatus,
  updateCooperationStatus,
  deleteCooperationStatus,
} from '@/api/cooperationStatuses'
import type { CooperationStatus } from '@/types'
import EmptyState from '@/components/EmptyState.vue'
import { formatDateTime } from '@/utils/formatters'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// ========== 状态管理 ==========
const loading = ref(false)
const cooperationStatuses = ref<CooperationStatus[]>([])

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
  { title: '合作状态名称', dataIndex: 'name', width: 200 },
  { title: '存储值', dataIndex: 'value', width: 160 },
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
  value: '',
  sort_order: 0,
})

const formRules = {
  name: [{ required: true, message: '请输入合作状态名称' }],
  value: [{ required: true, message: '请输入存储值' }],
  sort_order: [{ required: true, message: '请输入排序号' }],
}

// ========== 数据加载 ==========
const loadCooperationStatuses = async () => {
  loading.value = true
  try {
    const res = await getCooperationStatusesList()
    cooperationStatuses.value = res.data?.data || res.data || []
    pagination.total = cooperationStatuses.value.length
  } catch (error) {
    Message.error('加载合作状态失败')
    console.error('Failed to load cooperation statuses:', error)
  } finally {
    loading.value = false
  }
}

// ========== 事件处理 ==========
const handleCreate = () => {
  isEditMode.value = false
  editingId.value = null
  form.name = ''
  form.value = ''
  form.sort_order = 0
  modalVisible.value = true
}

const handleEdit = (record: CooperationStatus) => {
  isEditMode.value = true
  editingId.value = record.id
  form.name = record.name
  form.value = record.value
  form.sort_order = record.sort_order
  modalVisible.value = true
}

const handleSubmit = async () => {
  try {
    submitting.value = true
    if (isEditMode.value && editingId.value !== null) {
      await updateCooperationStatus(editingId.value, {
        name: form.name,
        value: form.value,
        sort_order: form.sort_order,
      })
      Message.success('更新成功')
    } else {
      await createCooperationStatus({
        name: form.name,
        value: form.value,
        sort_order: form.sort_order,
      })
      Message.success('创建成功')
    }
    await loadCooperationStatuses()
    return true
  } catch (error) {
    const msg = error instanceof Error ? error.message : '操作失败'
    Message.error(isEditMode.value ? `更新失败: ${msg}` : `创建失败: ${msg}`)
    console.error('Failed to save cooperation status:', error)
    return false
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await deleteCooperationStatus(id)
    Message.success('删除成功')
    await loadCooperationStatuses()
  } catch (error) {
    Message.error('删除失败')
    console.error('Failed to delete cooperation status:', error)
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
  loadCooperationStatuses()
})
</script>

<style scoped>
.cooperation-statuses-page {
  padding: 0; /* 移除 padding，由 Dashboard 统一提供 */
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
