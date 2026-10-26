<template>
  <div class="backup-management">
    <PageHeader eyebrow="System" title="数据备份" subtitle="数据库定时备份、清理与恢复" />

    <a-alert type="warning" style="margin-bottom: 24px">
      恢复备份将覆盖整个数据库，属于破坏性操作。建议在低峰期执行，恢复完成后需重启服务以刷新数据库连接池。
    </a-alert>

    <!-- 定时备份配置 -->
    <a-card :bordered="false" style="margin-bottom: 24px">
      <template #title>
        <div class="card-header">
          <span>定时备份配置</span>
        </div>
      </template>

      <a-form :model="scheduleForm" layout="vertical" style="max-width: 480px">
        <a-form-item label="启用每日自动备份">
          <a-switch v-model="scheduleForm.enabled" />
        </a-form-item>
        <a-form-item label="备份时间（HH:MM，24小时制）">
          <a-input v-model="scheduleForm.backup_time" placeholder="02:00" allow-clear />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button
              v-if="canManage"
              type="primary"
              :loading="savingSchedule"
              @click="handleSaveSchedule"
            >
              保存配置
            </a-button>
            <span v-if="schedule.next_run_time" class="next-run">
              下次执行时间：{{ schedule.next_run_time }}
            </span>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 手动备份 -->
    <a-card :bordered="false" style="margin-bottom: 24px">
      <template #title>
        <div class="card-header">
          <span>备份操作</span>
        </div>
      </template>

      <a-alert type="info" style="margin-bottom: 16px">
        手动备份为异步任务，点击后立即返回，请在下方「任务记录」中查看执行进度与结果。
      </a-alert>

      <a-button v-if="canManage" type="primary" :loading="performing" @click="handlePerformConfirm">
        立即备份
      </a-button>
    </a-card>

    <!-- 任务记录 -->
    <a-card :bordered="false">
      <template #title>
        <div class="card-header">
          <span>任务记录</span>
        </div>
      </template>

      <div class="table-toolbar">
        <a-select
          v-model="taskTypeFilter"
          style="width: 160px"
          placeholder="任务类型"
          allow-clear
          @change="handleFilterChange"
        >
          <a-option value="daily_backup">每日备份</a-option>
          <a-option value="manual_backup">手动备份</a-option>
          <a-option value="cleanup">过期清理</a-option>
          <a-option value="restore">恢复</a-option>
        </a-select>
        <a-button @click="fetchRecords">刷新</a-button>
      </div>

      <a-table
        :columns="columns"
        :data="records"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #task_type="{ record }">
          {{
            TASK_TYPE_LABELS[record.task_type as keyof typeof TASK_TYPE_LABELS] || record.task_type
          }}
        </template>
        <template #status="{ record }">
          <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
        </template>
        <template #backup_date="{ record }">
          {{ record.backup_date || '-' }}
        </template>
        <template #file_size_bytes="{ record }">
          {{ formatFileSize(record.file_size_bytes) }}
        </template>
        <template #duration_seconds="{ record }">
          {{ record.duration_seconds === null ? '-' : `${record.duration_seconds}s` }}
        </template>
        <template #operator_id="{ record }">
          {{ record.operator_id === null ? '系统自动' : `用户 ${record.operator_id}` }}
        </template>
        <template #retention_check_passed="{ record }">
          <span v-if="record.task_type !== 'cleanup'">-</span>
          <span v-else-if="record.retention_check_passed === null">-</span>
          <span v-else-if="record.retention_check_passed">校验通过</span>
          <span v-else style="color: var(--error)">校验未通过</span>
        </template>
        <template #deleted_count="{ record }">
          <span v-if="record.task_type !== 'cleanup'">-</span>
          <span v-else>{{ record.deleted_count }}</span>
        </template>
        <template #error_message="{ record }">
          <a-tooltip v-if="record.error_message" :content="record.error_message">
            <span class="error-text">{{ record.error_message }}</span>
          </a-tooltip>
          <span v-else>-</span>
        </template>
        <template #created_at="{ record }">
          {{ record.created_at || '-' }}
        </template>
        <template #actions="{ record }">
          <a-space v-if="isRestorable(record)">
            <a-button type="text" size="small" @click="handleDownload(record)">下载</a-button>
            <a-button
              type="text"
              size="small"
              status="danger"
              @click="handleRestoreConfirm(record)"
            >
              恢复
            </a-button>
          </a-space>
          <span v-else>-</span>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, reactive, ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { Message, Modal, Input as AInput } from '@arco-design/web-vue'
import service from '@/api'
import { handleError } from '@/utils/errorHandler'
import { useUserStore } from '@/stores/user'
import type { ApiResponse } from '@/types'

interface BackupSchedule {
  task_name: string
  enabled: boolean
  backup_time: string
  next_run_time: string | null
  updated_at: string | null
}

interface BackupRecord {
  id: number
  task_type: string
  status: string
  file_path: string | null
  file_size_bytes: number | null
  backup_date: string | null
  retention_check_passed: boolean | null
  deleted_count: number
  duration_seconds: number | null
  error_message: string | null
  operator_id: number | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
}

interface RecordsData {
  list: BackupRecord[]
  pagination: { total: number; page: number; page_size: number }
}

const userStore = useUserStore()
const canManage = computed(() => userStore.hasPermission('system:database_backup'))

const TASK_TYPE_LABELS = {
  daily_backup: '每日备份',
  manual_backup: '手动备份',
  cleanup: '过期清理',
  restore: '恢复',
} as const

const STATUS_COLORS: Record<string, string> = {
  success: 'green',
  failed: 'red',
  running: 'blue',
  pending: 'gray',
}

const STATUS_TEXTS: Record<string, string> = {
  success: '成功',
  failed: '失败',
  running: '执行中',
  pending: '等待中',
}

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/
const POLL_INTERVAL = 3000

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70 },
  { title: '类型', slotName: 'task_type', width: 100 },
  { title: '状态', slotName: 'status', width: 90 },
  { title: '备份日期', slotName: 'backup_date', width: 120 },
  { title: '文件大小', slotName: 'file_size_bytes', width: 110 },
  { title: '耗时', slotName: 'duration_seconds', width: 80 },
  { title: '操作人', slotName: 'operator_id', width: 100 },
  { title: '清理校验', slotName: 'retention_check_passed', width: 110 },
  { title: '删除数', slotName: 'deleted_count', width: 90 },
  { title: '错误信息', slotName: 'error_message', ellipsis: true },
  { title: '创建时间', slotName: 'created_at', width: 180 },
  { title: '操作', slotName: 'actions', width: 130, fixed: 'right' },
]

const loading = ref(false)
const performing = ref(false)
const savingSchedule = ref(false)

const schedule = ref<BackupSchedule>({
  task_name: 'daily_backup',
  enabled: false,
  backup_time: '02:00',
  next_run_time: null,
  updated_at: null,
})
const scheduleForm = reactive({ enabled: false, backup_time: '02:00' })

const records = ref<BackupRecord[]>([])
const taskTypeFilter = ref<string | undefined>(undefined)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

let pollTimer: number | undefined

const statusColor = (status: string) => STATUS_COLORS[status] || 'gray'
const statusText = (status: string) => STATUS_TEXTS[status] || status

const isRestorable = (record: BackupRecord) =>
  (record.task_type === 'daily_backup' || record.task_type === 'manual_backup') &&
  record.status === 'success'

const formatFileSize = (bytes: number | null) => {
  if (bytes === null || bytes === undefined) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

// ---------- 数据拉取 ----------

const fetchSchedule = async () => {
  try {
    const res = (await service.get(
      '/system/backup/schedule'
    )) as unknown as ApiResponse<BackupSchedule>
    if (res.code === 0 && res.data) {
      schedule.value = res.data
      scheduleForm.enabled = res.data.enabled
      scheduleForm.backup_time = res.data.backup_time
    }
  } catch (error) {
    handleError(error, '获取备份配置失败')
  }
}

const fetchRecords = async () => {
  loading.value = true
  try {
    const res = (await service.get('/system/backup/records', {
      params: {
        page: currentPage.value,
        page_size: pageSize.value,
        ...(taskTypeFilter.value ? { task_type: taskTypeFilter.value } : {}),
      },
    })) as unknown as ApiResponse<RecordsData>
    if (res.code === 0 && res.data) {
      records.value = res.data.list
      total.value = res.data.pagination.total
    }
  } catch (error) {
    handleError(error, '获取任务记录失败')
  } finally {
    loading.value = false
  }
}

const hasPendingTask = () =>
  records.value.some((r) => r.status === 'pending' || r.status === 'running')

const startPolling = () => {
  if (pollTimer !== undefined) return
  pollTimer = window.setInterval(() => {
    if (hasPendingTask()) {
      void fetchRecords()
    } else {
      stopPolling()
    }
  }, POLL_INTERVAL)
}

const stopPolling = () => {
  if (pollTimer !== undefined) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
}

// ---------- 配置 ----------

const handleSaveSchedule = async () => {
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(scheduleForm.backup_time)) {
    Message.error('备份时间格式应为 HH:MM（24小时制），如 02:00')
    return
  }
  savingSchedule.value = true
  try {
    const res = (await service.put('/system/backup/schedule', {
      enabled: scheduleForm.enabled,
      backup_time: scheduleForm.backup_time,
    })) as unknown as ApiResponse<BackupSchedule>
    if (res.code === 0) {
      Message.success('配置已保存')
      await fetchSchedule()
    } else {
      Message.error(res.message || '配置保存失败')
    }
  } catch (error) {
    handleError(error, '配置保存失败')
  } finally {
    savingSchedule.value = false
  }
}

// ---------- 手动备份 ----------

const handlePerformConfirm = () => {
  Modal.confirm({
    title: '确认立即备份',
    content: '将立即执行一次全量数据库备份（pg_dump），耗时可能较长。确定继续？',
    okText: '立即备份',
    cancelText: '取消',
    onBeforeOk: async () => {
      performing.value = true
      try {
        const res = (await service.post<BackupRecord>(
          '/system/backup/perform'
        )) as unknown as ApiResponse<BackupRecord>
        if (res.code === 0) {
          Message.success('备份任务已创建')
          await fetchRecords()
          startPolling()
        } else {
          Message.error(res.message || '创建备份任务失败')
        }
      } catch (error) {
        handleError(error, '创建备份任务失败')
      } finally {
        performing.value = false
      }
      return true
    },
  })
}

// ---------- 下载 ----------

const handleDownload = async (record: BackupRecord) => {
  try {
    const response = await service.get(`/system/backup/records/${record.id}/download`, {
      responseType: 'blob',
    })
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `backup_${record.backup_date || record.id}.dump`
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    handleError(error, '下载备份文件失败')
  }
}

// ---------- 恢复 ----------

const handleRestoreConfirm = (record: BackupRecord) => {
  let confirmDate = ''
  Modal.confirm({
    title: '确认恢复备份',
    content: () =>
      h('div', [
        h('p', { style: 'margin: 0 0 8px' }, '此操作将使用该备份覆盖整个数据库，且不可撤销。'),
        h('p', { style: 'margin: 0 0 8px' }, `请输入该备份的日期（${record.backup_date}）以确认：`),
        h(AInput, {
          placeholder: 'YYYY-MM-DD',
          allowClear: true,
          onInput: (val: string) => {
            confirmDate = val
          },
        }),
      ]),
    okText: '确认恢复',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    onBeforeOk: async () => {
      if (!DATE_PATTERN.test(confirmDate)) {
        Message.error('请输入正确的备份日期（YYYY-MM-DD）')
        return false
      }
      if (confirmDate !== record.backup_date) {
        Message.error('输入日期与该备份日期不一致')
        return false
      }
      try {
        const res = (await service.post<BackupRecord>(
          `/system/backup/records/${record.id}/restore`,
          { confirm_date: confirmDate }
        )) as unknown as ApiResponse<BackupRecord>
        if (res.code === 0) {
          Message.success('恢复任务已创建')
          await fetchRecords()
          startPolling()
          return true
        }
        Message.error(res.message || '创建恢复任务失败')
        return false
      } catch (error) {
        handleError(error, '创建恢复任务失败')
        return false
      }
    },
  })
}

// ---------- 分页 / 筛选 ----------

const handlePageChange = (page: number) => {
  currentPage.value = page
  void fetchRecords()
}

const handlePageSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  void fetchRecords()
}

const handleFilterChange = () => {
  currentPage.value = 1
  void fetchRecords()
}

onMounted(() => {
  void fetchSchedule()
  void fetchRecords()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.backup-management {
  padding: 0;
}

.card-header {
  font-size: 16px;
  font-weight: 600;
}

.next-run {
  color: var(--muted);
  font-size: 13px;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16px;
}

.error-text {
  display: inline-block;
  max-width: 200px;
  overflow: hidden;
  color: var(--error);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
