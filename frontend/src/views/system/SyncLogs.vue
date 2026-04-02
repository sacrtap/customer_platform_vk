<template>
  <div class="sync-logs-page">
    <a-page-header title="同步任务日志" subtitle="查看定时任务执行历史" />

    <a-card class="stats-card">
      <a-row :gutter="16">
        <a-col :span="6">
          <a-statistic title="总执行次数" :value="stats.total_tasks" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="成功率" :value="stats.success_rate" suffix="%" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="24 小时执行" :value="stats.last_24h.total" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="24 小时失败" :value="stats.last_24h.failed" :value-style="{ color: '#ff4d4f' }" />
        </a-col>
      </a-row>
    </a-card>

    <a-card class="filter-card">
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
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
          <a-button style="margin-left: 8px" @click="fetchLogs">
            <template #icon><icon-refresh /></template>
            刷新
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <a-card class="table-card">
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
    </a-card>
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

<style scoped lang="less">
.sync-logs-page {
  padding: 20px;

  .stats-card {
    margin-bottom: 16px;
  }

  .filter-card {
    margin-bottom: 16px;
  }

  .table-card {
    :deep(.arco-table-td) {
      padding: 12px 8px;
    }
  }

  .counts-cell {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 13px;

    .success {
      color: #00b42a;
    }

    .failed {
      color: #ff4d4f;
    }

    .skipped {
      color: #86909c;
    }
  }
}
</style>
