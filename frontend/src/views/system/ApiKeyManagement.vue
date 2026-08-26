<template>
  <div class="api-key-page">
    <PageHeader eyebrow="System" title="API-Key 管理" subtitle="管理开放平台 API 密钥">
      <template #actions>
        <a-button v-if="can('api_keys:manage')" type="primary" @click="handleCreate">
          申请 API-Key
        </a-button>
      </template>
    </PageHeader>

    <div class="table-section">
      <a-table
        :columns="columns"
        :data="apiKeys"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #status="{ record }">
          <a-tag :color="record.status === 'active' ? 'green' : 'red'">
            {{ record.status === 'active' ? '启用中' : '已停用' }}
          </a-tag>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button
              v-if="can('api_keys:manage')"
              type="text"
              size="small"
              @click="handleToggleStatus(record)"
            >
              {{ record.status === 'active' ? '停用' : '启用' }}
            </a-button>
            <a-popconfirm
              v-if="can('api_keys:manage')"
              content="确认删除该 API-Key？删除后将无法恢复。"
              @ok="handleDelete(record.id)"
            >
              <a-button type="text" size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无 API-Key" description="点击「申请 API-Key」创建第一个密钥">
            <template #action>
              <a-button v-if="can('api_keys:manage')" type="primary" @click="handleCreate">
                申请 API-Key
              </a-button>
            </template>
          </EmptyState>
        </template>
        <template #last_used_at="{ record }">
          {{ record.last_used_at ? formatDateTime(record.last_used_at) : '—' }}
        </template>
        <template #created_at="{ record }">
          {{ formatDateTime(record.created_at) }}
        </template>
      </a-table>
    </div>

    <!-- 申请 API-Key 对话框 -->
    <a-modal
      v-model:visible="modalVisible"
      title="申请 API-Key"
      :confirm-loading="submitting"
      width="500px"
      @before-ok="handleSubmit"
      @cancel="handleModalCancel"
    >
      <a-form ref="formRef" :model="form" :rules="formRules" layout="vertical">
        <a-form-item field="name" label="名称">
          <a-input v-model="form.name" placeholder="请输入名称，如「巧房 ERP 对接」" />
        </a-form-item>
        <a-form-item field="description" label="描述">
          <a-textarea
            v-model="form.description"
            placeholder="选填，描述该 Key 的用途"
            :auto-size="{ minRows: 2, maxRows: 4 }"
          />
        </a-form-item>
        <a-form-item field="expires_at" label="过期时间（选填）">
          <a-date-picker
            v-model="form.expires_at"
            show-time
            format="YYYY-MM-DD HH:mm:ss"
            placeholder="不填则永不过期"
            style="width: 100%"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 显示完整 Key 对话框（仅创建成功后显示一次） -->
    <a-modal
      v-model:visible="keyVisible"
      title="API-Key 创建成功"
      :ok-text="'我已复制'"
      :cancel-text="'关闭'"
      :mask-closable="false"
      @ok="handleKeyCopied"
    >
      <a-alert type="warning" style="margin-bottom: 16px">
        请立即复制并妥善保管以下 API-Key，关闭后将不再显示完整密钥。
      </a-alert>
      <a-input-group style="display: flex; gap: 8px">
        <a-input
          :model-value="newKey"
          readonly
          style="flex: 1; font-family: monospace"
          placeholder="API-Key"
        />
        <a-button type="primary" @click="copyKey(newKey)">
          <template #icon><icon-copy /></template>
          复制
        </a-button>
      </a-input-group>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import { getApiKeysList, createApiKey, toggleApiKeyStatus, deleteApiKey } from '@/api/apiKeys'
import type { ApiKey } from '@/types'
import { formatDateTime } from '@/utils/formatters'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// ========== 状态管理 ==========
const loading = ref(false)
const apiKeys = ref<ApiKey[]>([])

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
  { title: '名称', dataIndex: 'name', width: 180 },
  { title: 'Key', dataIndex: 'key_prefix', width: 160 },
  { title: '状态', slotName: 'status', width: 100, align: 'center' as const },
  { title: '描述', dataIndex: 'description', ellipsis: true, width: 200 },
  { title: '最后使用', slotName: 'last_used_at', width: 160 },
  { title: '创建时间', slotName: 'created_at', width: 160 },
  { title: '操作', slotName: 'action', width: 130, fixed: 'right' as const },
]

// ========== 表单 ==========
const modalVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  description: '',
  expires_at: '',
})

const formRules = {
  name: [{ required: true, message: '请输入 API-Key 名称' }],
}

// ========== Key 展示 ==========
const keyVisible = ref(false)
const newKey = ref('')

// ========== 数据加载 ==========
const loadApiKeys = async () => {
  loading.value = true
  try {
    const res = await getApiKeysList({
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    // 拦截器返回裸 JSON body {code, message, data, meta}
    const body = res as unknown as { data: ApiKey[]; meta: { total: number } }
    apiKeys.value = body?.data ?? []
    pagination.total = body?.meta?.total ?? body?.data?.length ?? 0
  } catch (error) {
    Message.error('加载 API-Key 列表失败')
    console.error('Failed to load API keys:', error)
  } finally {
    loading.value = false
  }
}

// ========== 事件处理 ==========
const handleCreate = () => {
  form.name = ''
  form.description = ''
  form.expires_at = ''
  modalVisible.value = true
}

const handleSubmit = async () => {
  try {
    submitting.value = true
    const data: { name: string; description?: string; expires_at?: string } = {
      name: form.name,
    }
    if (form.description) data.description = form.description
    if (form.expires_at) {
      const d = new Date(form.expires_at)
      data.expires_at = d.toISOString()
    }

    const res = await createApiKey(data)
    Message.success('API-Key 创建成功')

    // 显示完整 Key
    const created = res as unknown as { data: { key?: string }; key?: string }
    const createdKey = created.data?.key ?? created.key
    if (createdKey) {
      newKey.value = createdKey
      keyVisible.value = true
    }

    await loadApiKeys()
    return true
  } catch (error) {
    const msg = error instanceof Error ? error.message : '操作失败'
    Message.error(`创建失败: ${msg}`)
    console.error('Failed to create API key:', error)
    return false
  } finally {
    submitting.value = false
  }
}

const handleToggleStatus = async (record: ApiKey) => {
  try {
    await toggleApiKeyStatus(record.id)
    Message.success(record.status === 'active' ? '已停用' : '已启用')
    await loadApiKeys()
  } catch (error) {
    Message.error('操作失败')
    console.error('Failed to toggle API key status:', error)
  }
}

const handleDelete = async (id: number) => {
  try {
    await deleteApiKey(id)
    Message.success('删除成功')
    await loadApiKeys()
  } catch (error) {
    Message.error('删除失败')
    console.error('Failed to delete API key:', error)
  }
}

const copyKey = async (key: string) => {
  try {
    await navigator.clipboard.writeText(key)
    Message.success('已复制到剪贴板')
  } catch {
    Message.error('复制失败，请手动复制')
  }
}

const handleKeyCopied = () => {
  keyVisible.value = false
  newKey.value = ''
}

const handleModalCancel = () => {
  formRef.value?.resetFields()
}

const handlePageChange = (page: number) => {
  pagination.current = page
  loadApiKeys()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  loadApiKeys()
}

// ========== 生命周期 ==========
onMounted(() => {
  loadApiKeys()
})
</script>

<style scoped>
.api-key-page {
  padding: 0;
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
