<template>
  <div class="sync-logs-page">
    <div class="page-header">
      <div class="header-title">
        <h1>同步任务日志</h1>
        <p class="header-subtitle">查看定时任务执行历史</p>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">总执行次数</div>
        <div class="stat-value">{{ stats.total_tasks }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">成功率</div>
        <div class="stat-value success">{{ stats.success_rate }}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">24 小时执行</div>
        <div class="stat-value">{{ stats.last_24h.total }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">24 小时失败</div>
        <div class="stat-value danger">{{ stats.last_24h.failed }}</div>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="filter-section">
      <a-form layout="inline">
        <a-form-item label="任务名称">
          <a-select
            v-model="filters.task_name"
            placeholder="全部任务"
            style="width: 200px"
            allow-clear
          >
            <a-option value="sync_daily_usage">每日用量同步</a-option>
            <a-option value="generate_monthly_invoices">月度结算单生成</a-option>
            <a-option value="check_balance_warning">余额预警检查</a-option>
            <a-option value="send_overdue_emails">逾期提醒邮件</a-option>
            <a-option value="cleanup_temp_files">临时文件清理</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="状态">
          <a-select
            v-model="filters.status"
            placeholder="全部状态"
            style="width: 150px"
            allow-clear
          >
            <a-option value="success">成功</a-option>
            <a-option value="partial">部分成功</a-option>
            <a-option value="failed">失败</a-option>
          </a-select>
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
        <h3>执行记录</h3>
      </div>
      <a-table
        :columns="columns"
        :data="logs"
        :loading="loading"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #status="{ record }">
          <a-tag :color="getStatusColor(record.status)">
            {{ getStatusText(record.status) }}
          </a-tag>
        </template>
        <template #counts="{ record }">
          <div class="counts-cell">
            <span>总计：{{ record.total_count }}</span>
            <span class="success">成功：{{ record.success_count }}</span>
            <span class="failed">失败：{{ record.failed_count }}</span>
            <span class="skipped">跳过：{{ record.skipped_count }}</span>
          </div>
        </template>
        <template #executed_at="{ record }">
          {{ formatDate(record.executed_at) }}
        </template>
        <template #error_message="{ record }">
          <a-tooltip v-if="record.error_message" :content="record.error_message">
            <a-tag color="red" style="cursor: pointer">查看错误</a-tag>
          </a-tooltip>
          <span v-else>-</span>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import service from '@/api'

interface SyncLog {
  id: number
  task_name: string
  status: string
  total_count: number
  success_count: number
  failed_count: number
  skipped_count: number
  executed_at: string
  duration_seconds: number | null
  error_message: string | null
  created_at: string
}

interface Stats {
  total_tasks: number
  success_rate: number
  last_24h: {
    total: number
    success: number
    failed: number
  }
  by_task: Array<{
    task_name: string
    success: number
    failed: number
  }>
}

const loading = ref(false)
const logs = ref<SyncLog[]>([])
const stats = ref<Stats>({
  total_tasks: 0,
  success_rate: 0,
  last_24h: { total: 0, success: 0, failed: 0 },
  by_task: [],
})

const filters = reactive({
  task_name: '',
  status: '',
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const columns = [
  {
    title: '任务名称',
    dataIndex: 'task_name',
    slotName: 'task_name',
    width: 180,
  },
  {
    title: '状态',
    dataIndex: 'status',
    slotName: 'status',
    width: 100,
  },
  {
    title: '执行统计',
    slotName: 'counts',
    width: 200,
  },
  {
    title: '执行时间',
    dataIndex: 'executed_at',
    slotName: 'executed_at',
    width: 180,
  },
  {
    title: '耗时 (秒)',
    dataIndex: 'duration_seconds',
    width: 100,
  },
  {
    title: '错误信息',
    slotName: 'error_message',
    ellipsis: true,
    tooltip: true,
  },
]

const taskNameMap: Record<string, string> = {
  sync_daily_usage: '每日用量同步',
  generate_monthly_invoices: '月度结算单生成',
  check_balance_warning: '余额预警检查',
  send_overdue_emails: '逾期提醒邮件',
  cleanup_temp_files: '临时文件清理',
}

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    success: 'green',
    partial: 'orange',
    failed: 'red',
  }
  return colors[status] || 'gray'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    success: '成功',
    partial: '部分成功',
    failed: '失败',
  }
  return texts[status] || status
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return dateStr.replace('T', ' ').substring(0, 19)
}

const fetchStats = async () => {
  try {
    const res = await service.get('/sync-logs/stats')
    const data = res.data
    if (data.code === 0) {
      stats.value = data.data
    }
  } catch (error) {
    console.error('获取统计失败:', error)
  }
}

const fetchLogs = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      ...filters,
    }
    const res = await service.get('/sync-logs', { params })
    const data = res.data
    if (data.code === 0) {
      logs.value = data.data.list.map((log: SyncLog) => ({
        ...log,
        task_name: taskNameMap[log.task_name] || log.task_name,
      }))
      pagination.total = data.data.pagination.total
    }
  } catch (error) {
    Message.error('获取日志失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchLogs()
}

const handleReset = () => {
  filters.task_name = ''
  filters.status = ''
  pagination.current = 1
  fetchLogs()
}

const handlePageChange = (page: number) => {
  pagination.current = page
  fetchLogs()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchLogs()
}

onMounted(() => {
  fetchStats()
  fetchLogs()
})
</script>

<style scoped>
.sync-logs-page {
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  margin-bottom: 24px;
}

.stat-card {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  transition: all 200ms ease;
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-label {
  font-size: 13px;
  color: var(--neutral-6);
  margin-bottom: 12px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--neutral-10);
}

.stat-value.success {
  color: #22c55e;
}

.stat-value.danger {
  color: #ef4444;
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

.counts-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.counts-cell .success {
  color: #00b42a;
}

.counts-cell .failed {
  color: #ff4d4f;
}

.counts-cell .skipped {
  color: #86909c;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
