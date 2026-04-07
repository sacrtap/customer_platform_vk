<template>
  <div class="audit-logs-page">
    <div class="page-header">
      <div class="header-title">
        <h1>审计日志</h1>
        <p class="header-subtitle">查看系统操作记录</p>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="filter-section">
      <a-form layout="inline" :model="filters">
        <a-form-item label="用户">
          <a-input
            v-model="filters.user_id"
            placeholder="用户 ID"
            style="width: 120px"
            @press-enter="handleSearch"
          />
        </a-form-item>
        <a-form-item label="操作类型">
          <a-select
            v-model="filters.action"
            placeholder="全部操作"
            style="width: 150px"
            allow-clear
            @change="handleSearch"
          >
            <a-option v-for="action in actions" :key="action" :value="action">
              {{ action }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="模块">
          <a-select
            v-model="filters.module"
            placeholder="全部模块"
            style="width: 150px"
            allow-clear
            @change="handleSearch"
          >
            <a-option v-for="module in modules" :key="module" :value="module">
              {{ module }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="时间范围">
          <a-range-picker v-model="filters.dateRange" style="width: 240px" />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="handleSearch">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
            <a-button @click="fetchLogs">
              <template #icon>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  fill="currentColor"
                  viewBox="0 0 16 16"
                >
                  <path d="M8 3a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z" />
                  <path
                    d="m5.93 6.704-.847 6.783a1 1 0 0 0 1.094 1.12l1.13-1.13a1 1 0 0 1 1.394 0l1.13 1.13a1 1 0 0 0 1.094-1.12l-.847-6.783a1 1 0 0 0-.996-.876H6.926a1 1 0 0 0-.996.876zM6.002 1.5a2.5 2.5 0 0 1 4.996 0 2.5 2.5 0 0 1-4.996 0z"
                  />
                </svg>
              </template>
              刷新
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </div>

    <!-- 表格 -->
    <div class="table-section">
      <div class="table-header">
        <h3>操作记录</h3>
      </div>
      <a-table
        :columns="columns"
        :data="logs"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
      >
        <template #action="{ record }">
          <a-tag color="blue">{{ formatAction(record.action) }}</a-tag>
        </template>
        <template #module="{ record }">
          <a-tag>{{ record.module }}</a-tag>
        </template>
        <template #record="{ record }">
          <span v-if="record.record_type && record.record_id">
            {{ record.record_type }}#{{ record.record_id }}
          </span>
          <span v-else class="text-gray">-</span>
        </template>
        <template #changes="{ record }">
          <a-popover v-if="record.changes" position="left" trigger="click">
            <a-button type="text" size="small">查看详情</a-button>
            <template #content>
              <div class="changes-content">
                <div v-if="record.changes.before" class="change-section">
                  <strong>修改前:</strong>
                  <pre>{{ JSON.stringify(record.changes.before, null, 2) }}</pre>
                </div>
                <div v-if="record.changes.after" class="change-section">
                  <strong>修改后:</strong>
                  <pre>{{ JSON.stringify(record.changes.after, null, 2) }}</pre>
                </div>
              </div>
            </template>
          </a-popover>
          <span v-else class="text-gray">-</span>
        </template>
        <template #ip_address="{ record }">
          <a-typography-text code>{{ record.ip_address || '-' }}</a-typography-text>
        </template>
        <template #created_at="{ record }">
          {{ formatDate(record.created_at) }}
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as auditApi from '@/api/audit'

interface AuditLog {
  id: number
  user_id: number | null
  username: string
  action: string
  module: string
  record_id: number | null
  record_type: string | null
  changes: { before?: Record<string, unknown>; after?: Record<string, unknown> } | null
  ip_address: string | null
  created_at: string | null
}

const logs = ref<AuditLog[]>([])
const loading = ref(false)
const actions = ref<string[]>([])
const modules = ref<string[]>([])

const filters = reactive({
  user_id: '',
  action: '',
  module: '',
  dateRange: [] as Date[],
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const columns = [
  { title: 'ID', dataIndex: 'id', width: 80 },
  { title: '用户', dataIndex: 'username', width: 120 },
  { title: '操作类型', slotName: 'action', width: 150 },
  { title: '模块', slotName: 'module', width: 120 },
  { title: '操作对象', slotName: 'record', width: 150 },
  { title: '变更详情', slotName: 'changes', width: 120 },
  { title: 'IP 地址', slotName: 'ip_address', width: 140 },
  { title: '操作时间', slotName: 'created_at', width: 180, sortable: true },
]

const fetchLogs = async () => {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }

    if (filters.user_id) params.user_id = filters.user_id
    if (filters.action) params.action = filters.action
    if (filters.module) params.module = filters.module

    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_date = filters.dateRange[0].toISOString()
      params.end_date = filters.dateRange[1].toISOString()
    }

    const res = await auditApi.getAuditLogs(params)
    logs.value = res.data.list
    pagination.total = res.data.total
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '加载审计日志失败')
  } finally {
    loading.value = false
  }
}

const fetchActions = async () => {
  try {
    const res = await auditApi.getAuditActions()
    actions.value = res.data
  } catch (err: unknown) {
    console.error('加载操作类型失败:', err)
  }
}

const fetchModules = async () => {
  try {
    const res = await auditApi.getAuditModules()
    modules.value = res.data
  } catch (err: unknown) {
    console.error('加载模块失败:', err)
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchLogs()
}

const handleReset = () => {
  filters.user_id = ''
  filters.action = ''
  filters.module = ''
  filters.dateRange = []
  handleSearch()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchLogs()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchLogs()
}

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatAction = (action: string) => {
  const actionMap: Record<string, string> = {
    create: '创建',
    update: '更新',
    delete: '删除',
    login: '登录',
    logout: '登出',
    recharge: '充值',
    deduct: '扣款',
    submit: '提交',
    confirm: '确认',
    pay: '付款',
    complete: '完成',
  }
  return actionMap[action] || action
}

onMounted(() => {
  fetchLogs()
  fetchActions()
  fetchModules()
})
</script>

<style scoped>
.audit-logs-page {
  padding: 0;
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-10: #1d2330;
  --primary-6: #0369a1;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.page-header {
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

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--neutral-2);
}

.table-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--neutral-10);
}

.text-gray {
  color: var(--neutral-5);
}

.changes-content {
  max-width: 400px;
  max-height: 300px;
  overflow: auto;
}

.change-section {
  margin-bottom: 12px;
}

.change-section pre {
  background: var(--neutral-1);
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  margin: 4px 0;
}
</style>
