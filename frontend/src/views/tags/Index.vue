<template>
  <div class="tag-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>标签管理</h1>
        <p class="header-subtitle">自定义标签分类与管理</p>
      </div>
      <div class="header-actions">
        <a-button v-if="can('tags:create')" type="primary" @click="handleCreate">
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
          新建标签
        </a-button>
      </div>
    </div>

    <div class="tabs-section">
      <a-tabs v-model:active-key="activeTab" @change="handleTabChange">
        <a-tab-pane key="customer" title="客户标签">
          <div class="tag-list">
            <template v-if="loading">
              <div class="loading-container">
                <a-spin />
              </div>
            </template>
            <template v-else>
              <a-tag
                v-for="tag in customerTags"
                :key="tag.id"
                color="arcoblue"
                size="large"
                closable
                style="cursor: pointer"
                @close="can('tags:delete') && handleDelete(tag.id)"
                @click="can('tags:edit') && openEditModal(tag)"
              >
                {{ tag.name }}
              </a-tag>
              <a-empty v-if="customerTags.length === 0" description="暂无标签" />
            </template>
          </div>
        </a-tab-pane>
        <a-tab-pane key="profile" title="画像标签">
          <div class="tag-list">
            <template v-if="loading">
              <div class="loading-container">
                <a-spin />
              </div>
            </template>
            <template v-else>
              <a-tag
                v-for="tag in profileTags"
                :key="tag.id"
                color="green"
                size="large"
                closable
                style="cursor: pointer"
                @close="can('tags:delete') && handleDelete(tag.id)"
                @click="can('tags:edit') && openEditModal(tag)"
              >
                {{ tag.name }}
              </a-tag>
              <a-empty v-if="profileTags.length === 0" description="暂无标签" />
            </template>
          </div>
        </a-tab-pane>
      </a-tabs>

      <div v-if="pagination.total > 0" class="pagination-section">
        <a-pagination
          :current="pagination.current"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          :show-total="true"
          :show-page-size="true"
          @page-change="handlePageChange"
          @page-size-change="handlePageSizeChange"
        />
      </div>
    </div>

    <!-- 标签编辑对话框 -->
    <a-modal
      v-model:visible="tagModalVisible"
      :title="isEditMode ? '编辑标签' : '新建标签'"
      :confirm-loading="submitting"
      width="500px"
      @before-ok="handleTagSubmit"
      @cancel="handleTagModalCancel"
    >
      <a-form ref="tagFormRef" :model="tagForm" :rules="tagFormRules" layout="vertical">
        <a-form-item field="name" label="标签名称">
          <a-input v-model="tagForm.name" placeholder="请输入标签名称" />
        </a-form-item>
        <a-form-item v-if="!isEditMode" field="type" label="标签类型">
          <a-radio-group v-model="tagForm.type">
            <a-radio value="customer">客户标签</a-radio>
            <a-radio value="profile">画像标签</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item field="category" label="标签分类（可选）">
          <a-input v-model="tagForm.category" placeholder="请输入标签分类" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import { getTags, createTag, updateTag, deleteTag, type Tag as ApiTag } from '@/api/tags'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// ========== 类型定义 ==========
interface Tag extends ApiTag {
  usage_count?: number
}

// ========== 状态管理 ==========
const loading = ref(false)
const activeTab = ref<'customer' | 'profile'>('customer')
const allTags = ref<Tag[]>([])

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

// 计算属性：根据 activeTab 过滤标签
const customerTags = computed(() => allTags.value.filter((tag) => tag.type === 'customer'))
const profileTags = computed(() => allTags.value.filter((tag) => tag.type === 'profile'))

// ========== 标签表单 ==========
const tagModalVisible = ref(false)
const isEditMode = ref(false)
const submitting = ref(false)
const tagFormRef = ref<FormInstance>()
const editingTagId = ref<number | null>(null)

const tagForm = reactive({
  name: '',
  type: 'customer' as 'customer' | 'profile',
  category: '',
})

const tagFormRules = {
  name: [
    { required: true, message: '请输入标签名称' },
    { minLength: 1, maxLength: 50, message: '标签名称长度 1-50 个字符' },
  ],
  type: [{ required: true, message: '请选择标签类型' }],
}

// ========== 数据加载 ==========
const loadTags = async () => {
  loading.value = true
  try {
    const res = await getTags({
      page: pagination.current,
      page_size: pagination.pageSize,
      type: activeTab.value,
    })

    const tagsList = (res.data as Record<string, unknown>).list as Tag[] || []
    pagination.total = ((res.data as Record<string, unknown>).total as number) || 0
    allTags.value = tagsList
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载标签列表失败')
  } finally {
    loading.value = false
  }
}

// ========== 事件处理 ==========
const handleTabChange = (key: string) => {
  activeTab.value = key as 'customer' | 'profile'
  pagination.current = 1
  loadTags()
}

const handlePageChange = (page: number) => {
  pagination.current = page
  loadTags()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  loadTags()
}

const handleCreate = () => {
  isEditMode.value = false
  editingTagId.value = null
  Object.assign(tagForm, {
    name: '',
    type: activeTab.value,
    category: '',
  })
  tagModalVisible.value = true
}

// 打开编辑对话框
const openEditModal = (tag: Tag) => {
  isEditMode.value = true
  editingTagId.value = tag.id
  Object.assign(tagForm, {
    name: tag.name,
    type: tag.type,
    category: tag.category || '',
  })
  tagModalVisible.value = true
}

const handleTagModalCancel = () => {
  tagModalVisible.value = false
  tagFormRef.value?.resetFields()
}

const handleTagSubmit = async () => {
  try {
    await tagFormRef.value?.validate()
  } catch {
    return false
  }

  submitting.value = true
  try {
    if (isEditMode.value && editingTagId.value) {
      await updateTag(editingTagId.value, {
        name: tagForm.name,
        category: tagForm.category || undefined,
      })
      Message.success('标签更新成功')
    } else {
      await createTag({
        name: tagForm.name,
        type: tagForm.type,
        category: tagForm.category || undefined,
      })
      Message.success('标签创建成功')
    }
    // 等待刷新完成，确保数据已加载
    await loadTags()
    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '操作失败')
    return false
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await deleteTag(id)
    Message.success('删除成功')
    // 等待刷新完成
    await loadTags()
  } catch (error: unknown) {
    Message.error((error as Error).message || '删除失败')
  }
}

onMounted(() => {
  loadTags()
})
</script>

<style scoped>
.tag-management-page {
  padding: 0; /* 移除 padding，由 Dashboard 统一提供 */
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-6: #646a73;
  --neutral-10: #1d2330;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
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

.tabs-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  padding: 24px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 0;
  min-height: 60px;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  min-height: 100px;
}

.pagination-section {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--neutral-2);
  display: flex;
  justify-content: center;
}
</style>
