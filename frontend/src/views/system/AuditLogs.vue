<template>
  <div class="audit-logs-page">
    <PageHeader eyebrow="System" title="审计日志" subtitle="查看系统操作记录" />

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
          <a-tooltip v-if="record.description?.action_label" :content="record.action">
            <a-tag color="blue">{{ record.description.action_label }}</a-tag>
          </a-tooltip>
          <a-tag v-else color="blue">{{ record.action }}</a-tag>
        </template>
        <template #module="{ record }">
          <a-tooltip v-if="record.description?.module_label" :content="record.module">
            <a-tag>{{ record.description.module_label }}</a-tag>
          </a-tooltip>
          <a-tag v-else>{{ record.module }}</a-tag>
        </template>
        <template #record="{ record }">
          <span v-if="record.record_type && record.record_id">
            {{ record.description?.record_type_label || record.record_type }}#{{ record.record_id }}
          </span>
          <span v-else-if="record.module" class="text-gray">
            {{ record.description?.module_label || record.module
            }}<span v-if="record.operation_type === 'batch'"> (批量)</span>
          </span>
          <span v-else class="text-gray">-</span>
        </template>
        <template #changes="{ record }">
          <a-button v-if="hasDetail(record)" type="text" size="small" @click="openDetail(record)">
            查看详情
          </a-button>
          <span v-else class="text-gray">-</span>
        </template>
        <template #ip_address="{ record }">
          <a-typography-text code>{{ record.ip_address || '-' }}</a-typography-text>
        </template>
        <template #created_at="{ record }">
          {{ formatDateTime(record.created_at) }}
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:visible="detailVisible"
      :title="detailTitle"
      :footer="false"
      width="min(760px, calc(100vw - 32px))"
      unmount-on-close
    >
      <div v-if="detailRecord" class="audit-detail">
        <div class="detail-meta">
          <span>操作人：{{ detailRecord.username || '—' }}</span>
          <span>时间：{{ formatDateTime(detailRecord.created_at) }}</span>
          <span>IP：{{ detailRecord.ip_address || '—' }}</span>
          <span v-if="detailRecord.operation_type">
            操作方式：{{
              OPERATION_TYPE_LABELS[detailRecord.operation_type] || detailRecord.operation_type
            }}
          </span>
        </div>

        <ul v-if="detailRecord.description?.summary?.length" class="detail-summary">
          <li v-for="(line, index) in detailRecord.description.summary" :key="index">
            {{ line }}
          </li>
        </ul>

        <table v-if="detailFields.length" class="detail-fields">
          <thead>
            <tr>
              <th class="field-name">字段</th>
              <th>变更前</th>
              <th>变更后</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in detailFields" :key="index">
              <td class="field-name">{{ row.label }}</td>
              <td class="field-value">{{ row.before }}</td>
              <td class="field-value">{{ row.after }}</td>
            </tr>
          </tbody>
        </table>

        <a-collapse :bordered="false" class="detail-raw">
          <a-collapse-item key="raw" header="原始变更数据（JSON）">
            <pre>{{ rawDetail }}</pre>
          </a-collapse-item>
        </a-collapse>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as auditApi from '@/api/audit'
import PageHeader from '@/components/PageHeader.vue'
import { formatDateTime } from '@/utils/formatters'

interface AuditFieldRow {
  label: string
  before: string
  after: string
}

/** 后端 describe_audit 产出的中文描述（展示层解释，不改原始 changes） */
interface AuditDescription {
  action_label: string
  module_label: string
  record_type_label: string | null
  summary: string[]
  fields: AuditFieldRow[]
}

interface AuditLog {
  id: number
  user_id: number | null
  username: string
  action: string
  module: string
  record_id: number | null
  record_type: string | null
  changes: Record<string, unknown> | null
  description: AuditDescription | null
  ip_address: string | null
  created_at: string | null
  operation_type: string | null // standard/batch/relation/sensitive
  extra_metadata: Record<string, unknown> | null
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
  { title: '操作类型', slotName: 'action', width: 160 },
  { title: '模块', slotName: 'module', width: 120 },
  { title: '操作对象', slotName: 'record', width: 150 },
  { title: '变更详情', slotName: 'changes', width: 120 },
  { title: 'IP 地址', slotName: 'ip_address', width: 140 },
  { title: '操作时间', slotName: 'created_at', width: 180, sortable: true },
]

const OPERATION_TYPE_LABELS: Record<string, string> = {
  standard: '标准操作',
  batch: '批量操作',
  relation: '关联操作',
  sensitive: '敏感操作',
}

const detailVisible = ref(false)
const detailRecord = ref<AuditLog | null>(null)

const detailFields = computed<AuditFieldRow[]>(() => detailRecord.value?.description?.fields ?? [])

const detailTitle = computed(() => {
  const d = detailRecord.value?.description
  const action = d?.action_label || detailRecord.value?.action || '操作'
  const type = d?.record_type_label || detailRecord.value?.record_type
  const id = detailRecord.value?.record_id
  return id ? `${action} · ${type ?? ''}#${id}` : action
})

const rawDetail = computed(() => {
  const record = detailRecord.value
  if (!record) return ''
  return JSON.stringify(
    {
      changes: record.changes,
      extra_metadata: record.extra_metadata,
      operation_type: record.operation_type,
    },
    null,
    2
  )
})

const hasDetail = (record: AuditLog) =>
  Boolean(record.changes || record.extra_metadata || record.description?.summary?.length)

const openDetail = (record: AuditLog) => {
  detailRecord.value = record
  detailVisible.value = true
}

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

onMounted(() => {
  fetchLogs()
  fetchActions()
  fetchModules()
})
</script>

<style scoped>
.audit-logs-page {
  padding: 0;
}

.page-header {
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 8px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--muted);
}

.filter-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--soft);
  box-shadow: var(--shadow-sm);
  margin-bottom: 24px;
}

.table-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--soft);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--soft);
}

.table-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
}

.text-gray {
  color: #94a3b8;
}

.audit-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--soft);
  color: var(--muted);
  font-size: 13px;
}

.detail-summary {
  margin: 0;
  padding-left: 18px;
  color: var(--ink);
  font-size: 14px;
  line-height: 1.9;
}

.detail-fields {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.detail-fields th,
.detail-fields td {
  border: 1px solid var(--soft);
  padding: 8px 12px;
  text-align: left;
  vertical-align: top;
  word-break: break-word;
}

.detail-fields th {
  background: var(--bg);
  font-weight: 600;
  color: var(--muted);
  white-space: nowrap;
}

.detail-fields .field-name {
  width: 132px;
  color: var(--muted);
  white-space: nowrap;
}

.detail-fields .field-value {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  color: var(--ink);
}

.detail-raw {
  background: transparent;
}

.detail-raw pre {
  margin: 0;
  background: var(--bg);
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.7;
  max-height: 280px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
