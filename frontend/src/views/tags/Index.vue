<template>
  <div class="tag-list">
    <a-card>
      <template #title>
        <a-space>
          <span>标签管理</span>
          <a-button type="primary" @click="showCreateModal">
            <template #icon><icon-plus /></template>
            新建标签
          </a-button>
        </a-space>
      </template>

      <!-- 筛选区域 -->
      <a-form :model="filters" layout="inline" class="filter-form">
        <a-form-item label="标签类型">
          <a-select v-model="filters.type" placeholder="请选择" style="width: 150px" allow-clear>
            <a-option value="customer">客户标签</a-option>
            <a-option value="profile">画像标签</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="标签分类">
          <a-input v-model="filters.category" placeholder="请输入分类" style="width: 150px" allow-clear />
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
          <a-tag :color="record.type === 'customer' ? 'blue' : 'purple'">
            {{ record.name }}
          </a-tag>
        </template>
        <template #type="{ record }">
          <a-tag :color="record.type === 'customer' ? 'blue' : 'purple'">
            {{ record.type === 'customer' ? '客户标签' : '画像标签' }}
          </a-tag>
        </template>
        <template #category="{ record }">
          <a-tag v-if="record.category" color="gray">{{ record.category }}</a-tag>
          <span v-else>-</span>
        </template>
        <template #usage="{ record }">
          <a-space v-if="record.usage_count">
            <a-tag color="blue" size="small">客户：{{ record.usage_count.customer_count }}</a-tag>
            <a-tag color="purple" size="small">画像：{{ record.usage_count.profile_count }}</a-tag>
          </a-space>
          <span v-else>-</span>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="viewUsage(record)">使用统计</a-button>
            <a-button type="text" size="small" @click="showEditModal(record)">编辑</a-button>
            <a-popconfirm
              content="确定要删除此标签吗？删除后已关联的客户将失去此标签。"
              @ok="handleDelete(record)"
            >
              <a-button type="text" size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <!-- 创建/编辑标签弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :confirm-loading="modalLoading"
      width="500px"
      @ok="handleSubmit"
    >
      <a-form :model="formData" layout="vertical">
        <a-form-item
          label="标签名称"
          :rules="[{ required: true, message: '请输入标签名称' }]"
        >
          <a-input v-model="formData.name" placeholder="请输入标签名称" />
        </a-form-item>
        <a-form-item
          label="标签类型"
          :rules="[{ required: true, message: '请选择标签类型' }]"
        >
          <a-select v-model="formData.type" placeholder="请选择标签类型" :disabled="isEdit">
            <a-option value="customer">客户标签</a-option>
            <a-option value="profile">画像标签</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="标签分类">
          <a-input v-model="formData.category" placeholder="请输入标签分类（可选）" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 使用统计弹窗 -->
    <a-modal v-model:visible="usageModalVisible" title="标签使用统计" :footer="false">
      <a-descriptions :column="1" bordered>
        <a-descriptions-item label="标签名称">{{ selectedTag?.name }}</a-descriptions-item>
        <a-descriptions-item label="标签类型">
          <a-tag :color="selectedTag?.type === 'customer' ? 'blue' : 'purple'">
            {{ selectedTag?.type === 'customer' ? '客户标签' : '画像标签' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="关联客户数">
          <a-typography-text :type="usageData?.customer_count ? 'success' : 'secondary'">
            {{ usageData?.customer_count || 0 }}
          </a-typography-text>
        </a-descriptions-item>
        <a-descriptions-item label="关联画像数">
          <a-typography-text :type="usageData?.profile_count ? 'success' : 'secondary'">
            {{ usageData?.profile_count || 0 }}
          </a-typography-text>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus } from '@arco-design/web-vue/es/icon'
import * as tagApi from '@/api/tags'

interface Tag {
  id: number
  name: string
  type: 'customer' | 'profile'
  category?: string
  created_by?: number
  created_at?: string
  usage_count?: {
    customer_count: number
    profile_count: number
  }
}

const columns = [
  { title: '标签名称', dataIndex: 'name', slotName: 'name', width: 200 },
  { title: '标签类型', dataIndex: 'type', slotName: 'type', width: 120 },
  { title: '标签分类', dataIndex: 'category', slotName: 'category', width: 120 },
  { title: '使用统计', slotName: 'usage', width: 200 },
  { title: '操作', slotName: 'action', width: 200, fixed: 'right' },
]

const data = ref<Tag[]>([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const filters = reactive({
  type: undefined as 'customer' | 'profile' | undefined,
  category: '',
})

const modalVisible = ref(false)
const modalTitle = ref('新建标签')
const modalLoading = ref(false)
const isEdit = ref(false)

const formData = reactive({
  id: null as number | null,
  name: '',
  type: undefined as 'customer' | 'profile' | undefined,
  category: '',
})

const usageModalVisible = ref(false)
const selectedTag = ref<Tag | null>(null)
const usageData = ref<{ customer_count: number; profile_count: number } | null>(null)

const fetchData = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filters.type) params.type = filters.type
    if (filters.category) params.category = filters.category

    const res = await tagApi.getTags(params)
    data.value = res.data.list
    pagination.total = res.data.total
  } catch (err: any) {
    Message.error(err.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchData()
}

const handleReset = () => {
  filters.type = undefined
  filters.category = ''
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
  modalTitle.value = '新建标签'
  Object.assign(formData, {
    id: null,
    name: '',
    type: undefined,
    category: '',
  })
  modalVisible.value = true
}

const showEditModal = (record: Tag) => {
  isEdit.value = true
  modalTitle.value = '编辑标签'
  Object.assign(formData, {
    id: record.id,
    name: record.name,
    type: record.type,
    category: record.category || '',
  })
  modalVisible.value = true
}

const handleSubmit = async () => {
  if (!formData.name || !formData.type) {
    Message.warning('请填写必填项')
    return
  }

  modalLoading.value = true
  try {
    if (isEdit.value && formData.id) {
      await tagApi.updateTag(formData.id, {
        name: formData.name,
        category: formData.category || undefined,
      })
      Message.success('更新成功')
    } else {
      await tagApi.createTag({
        name: formData.name,
        type: formData.type as 'customer' | 'profile',
        category: formData.category || undefined,
      })
      Message.success('创建成功')
    }
    modalVisible.value = false
    fetchData()
  } catch (err: any) {
    Message.error(err.message || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

const handleDelete = async (record: Tag) => {
  try {
    await tagApi.deleteTag(record.id)
    Message.success('删除成功')
    fetchData()
  } catch (err: any) {
    Message.error(err.message || '删除失败')
  }
}

const viewUsage = async (record: Tag) => {
  selectedTag.value = record
  try {
    const res = await tagApi.getTagUsage(record.id)
    usageData.value = res.data
    usageModalVisible.value = true
  } catch (err: any) {
    Message.error(err.message || '加载失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.tag-list {
  padding: 20px;
}

.filter-form {
  margin-bottom: 16px;
}
</style>
