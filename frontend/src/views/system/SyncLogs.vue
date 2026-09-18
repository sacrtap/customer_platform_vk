<template>
  <div class="sync-logs-page">
    <PageHeader eyebrow="System" title="同步任务日志" subtitle="查看同步任务执行历史和状态" />

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">总任务数</div>
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

    <!-- 定时同步配置 -->
    <div class="schedule-card">
      <div class="schedule-header">
        <h3>定时同步配置</h3>
        <span class="schedule-desc">每日自动同步（订单同步 + 费用计算一体化），同步昨天数据</span>
      </div>
      <div class="schedule-body">
        <div class="schedule-item">
          <span class="schedule-label">启用定时同步</span>
          <a-switch v-if="canEditSchedule" v-model="schedule.enabled" :disabled="savingSchedule" />
          <a-tag v-else :color="schedule.enabled ? 'green' : 'gray'">
            {{ schedule.enabled ? '已启用' : '已停用' }}
          </a-tag>
        </div>
        <div class="schedule-item">
          <span class="schedule-label">执行时间</span>
          <a-time-picker
            v-if="canEditSchedule"
            v-model="schedule.sync_time"
            format="HH:mm"
            value-format="HH:mm"
            :disabled="savingSchedule"
            style="width: 140px"
          />
          <span v-else class="schedule-value">{{ schedule.sync_time }}</span>
        </div>
        <div class="schedule-item">
          <span class="schedule-label">同步模式</span>
          <a-select
            v-if="canEditSchedule"
            v-model="schedule.sync_mode"
            :disabled="savingSchedule"
            style="width: 180px"
          >
            <a-option value="skip_existing">仅同步无数据</a-option>
            <a-option value="force_overwrite">强制覆盖已有数据</a-option>
          </a-select>
          <span v-else class="schedule-value">
            {{ schedule.sync_mode === 'skip_existing' ? '仅同步无数据' : '强制覆盖' }}
          </span>
        </div>
        <div class="schedule-item schedule-next">
          <span class="schedule-label">下次执行</span>
          <span class="schedule-value">{{ getNextRunText() }}</span>
        </div>
        <a-button
          v-if="canEditSchedule"
          type="primary"
          :loading="savingSchedule"
          @click="handleSaveSchedule"
        >
          保存配置
        </a-button>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="filter-section">
      <a-form layout="inline">
        <a-form-item label="任务状态">
          <a-select
            v-model="filters.status"
            placeholder="全部状态"
            style="width: 200px"
            allow-clear
          >
            <a-option value="pending">队列中</a-option>
            <a-option value="running">执行中</a-option>
            <a-option value="completed">已完成</a-option>
            <a-option value="partial">部分完成</a-option>
            <a-option value="cancelled">已取消</a-option>
            <a-option value="failed">失败</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="handleSearch">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
            <a-button @click="() => fetchTasks()">
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
        <h3>任务记录</h3>
      </div>
      <a-table
        :columns="columns"
        :data="tasks"
        :loading="loading"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #task_id="{ record }">
          {{ record.task_id.substring(0, 8) }}
        </template>
        <template #period="{ record }"> {{ record.start_date }} ~ {{ record.end_date }} </template>
        <template #sync_mode="{ record }">
          {{ record.sync_mode === 'skip_existing' ? '仅同步无数据' : '强制覆盖' }}
        </template>
        <template #status="{ record }">
          <a-tag :color="getStatusColor(record)">
            {{ getStatusText(record.status) }}
          </a-tag>
        </template>
        <template #progress="{ record }">
          <div v-if="record.status === 'running'" class="progress-cell">
            <a-progress
              :percent="Math.round((record.completed_days / record.total_days) * 100)"
              :status="getProgressStatus(record.status)"
              :show-text="false"
              size="small"
            />
            <span class="progress-text">
              {{ record.completed_days }}/{{ record.total_days }} 天
            </span>
          </div>
          <span v-else-if="record.status === 'completed' || record.status === 'partial'">
            {{ record.completed_days }}/{{ record.total_days }} 天
            <span v-if="record.failed_count > 0" style="color: var(--red); font-size: 12px">
              (失败 {{ record.failed_count }})
            </span>
          </span>
          <span v-else>-</span>
        </template>
        <template #created_at="{ record }">
          {{ formatDate(record.created_at) }}
        </template>
        <template #completed_at="{ record }">
          {{ record.completed_at ? formatDate(record.completed_at) : '-' }}
        </template>
        <template #operator="{ record }">
          <span v-if="record.operator_id === null || record.operator_id === undefined"
            >系统自动</span
          >
          <span v-else>{{ record.operator_name || '-' }}</span>
        </template>
        <template #execution_info="{ record }">
          <a-tag v-if="record.status === 'pending' || record.status === 'running'" color="gray"
            >-</a-tag
          >
          <a-tag
            v-else
            :color="getExecutionColor(record)"
            style="cursor: pointer"
            @click="openDetail(record)"
          >
            {{ getExecutionText(record) }}
          </a-tag>
        </template>
        <template #actions="{ record }">
          <a-button
            v-if="record.status === 'pending' || record.status === 'running'"
            type="text"
            size="small"
            status="danger"
            @click="handleCancel(record)"
          >
            取消任务
          </a-button>
        </template>
      </a-table>
    </div>

    <!-- 执行信息详情 -->
    <SyncLogDetailDrawer v-model:visible="drawerVisible" :task="selectedTask" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import { getSyncSchedule, updateSyncSchedule, type SyncSchedule } from '@/api/syncSchedule'
import {
  getSyncTaskList,
  getSyncTaskStats,
  cancelSyncTask,
  type SyncTask,
  type SyncTaskStats,
} from '@/api/syncTasks'
import SyncLogDetailDrawer from './components/SyncLogDetailDrawer.vue'

interface Task extends SyncTask {
  operator_name?: string
}

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)
const canEditSchedule = can('system:sync_schedule')

const loading = ref(false)
const tasks = ref<Task[]>([])
const stats = ref<SyncTaskStats>({
  total_tasks: 0,
  success_rate: 0,
  last_24h: { total: 0, failed: 0 },
})

const filters = reactive({
  status: '',
})

// 定时同步配置
const schedule = reactive<SyncSchedule>({
  task_name: 'daily_sync',
  enabled: false,
  sync_time: '01:00',
  sync_mode: 'skip_existing',
  next_run_time: null,
  updated_at: null,
})
const savingSchedule = ref(false)

// 执行信息详情 Drawer
const drawerVisible = ref(false)
const selectedTask = ref<Task | null>(null)

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const columns = [
  {
    title: '任务 ID',
    slotName: 'task_id',
    width: 100,
  },
  {
    title: '同步周期',
    slotName: 'period',
    width: 200,
  },
  {
    title: '同步模式',
    slotName: 'sync_mode',
    width: 120,
  },
  {
    title: '状态',
    slotName: 'status',
    width: 100,
  },
  {
    title: '进度',
    slotName: 'progress',
    width: 180,
  },
  {
    title: '创建时间',
    slotName: 'created_at',
    width: 180,
  },
  {
    title: '完成时间',
    slotName: 'completed_at',
    width: 180,
  },
  {
    title: '操作人',
    slotName: 'operator',
    width: 120,
  },
  {
    title: '执行信息',
    slotName: 'execution_info',
    width: 100,
  },
  {
    title: '操作',
    slotName: 'actions',
    width: 120,
    fixed: 'right',
  },
]

const getStatusColor = (record: Task) => {
  const status = record.status
  // 旧数据兼容：completed 但有失败天数，显示金色警告
  if (status === 'completed' && record.failed_count > 0) return 'gold'
  const colors: Record<string, string> = {
    pending: 'blue',
    running: 'green',
    completed: 'gray',
    partial: 'gold',
    cancelled: 'orange',
    failed: 'red',
  }
  return colors[status] || 'gray'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '队列中',
    running: '执行中',
    completed: '已完成',
    partial: '部分完成',
    cancelled: '已取消',
    failed: '失败',
  }
  return texts[status] || status
}
const getProgressStatus = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'partial') return 'warning'
  if (status === 'failed') return 'danger'
  if (status === 'cancelled') return 'warning'
  return 'normal' // running/pending 显示蓝色
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return dateStr.replace('T', ' ').substring(0, 19)
}

const getNextRunText = () => {
  if (schedule.next_run_time) return formatDate(schedule.next_run_time)
  return schedule.enabled ? '已注册' : '未启用'
}

const getExecutionColor = (record: Task) => {
  if (record.status === 'cancelled') return 'gray'
  const status = record.execution_status
  if (status === 'error') return 'red'
  if (status === 'warning') return 'gold'
  // 兜底：历史任务无明细时 completed + failed_count>0 不应显示绿色"正常"
  if (record.status === 'completed' && (record.failed_count ?? 0) > 0) return 'gold'
  return 'green'
}

const getExecutionText = (record: Task) => {
  if (record.status === 'cancelled') return '已取消'
  const status = record.execution_status
  if (status === 'error') return '错误'
  if (status === 'warning') return '警告'
  // 兜底：completed + failed_count>0 回退为"警告"
  if (record.status === 'completed' && (record.failed_count ?? 0) > 0) return '警告'
  return '正常'
}

const openDetail = (record: Task) => {
  selectedTask.value = record
  drawerVisible.value = true
}

const fetchStats = async () => {
  try {
    const data = await getSyncTaskStats()
    stats.value = data
  } catch (error) {
    console.error('获取统计失败:', error)
  }
}

const fetchTasks = async (showLoading = true) => {
  if (showLoading) {
    loading.value = true
  }
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      status: filters.status || undefined,
    }
    const data = await getSyncTaskList(params)
    tasks.value = data.list
    pagination.total = data.pagination.total
  } catch (error) {
    if (showLoading) {
      Message.error('获取任务列表失败')
    }
    console.error(error)
  } finally {
    if (showLoading) {
      loading.value = false
    }
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchTasks()
}

const handleReset = () => {
  filters.status = ''
  pagination.current = 1
  fetchTasks()
}

const handlePageChange = (page: number) => {
  pagination.current = page
  fetchTasks()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchTasks()
}

const handleCancel = async (task: Task) => {
  Modal.warning({
    title: '确认取消任务',
    content: '确定要取消该同步任务吗？取消后任务将停止执行，已同步的数据不会回滚。',
    okText: '确定取消',
    cancelText: '返回',
    okButtonProps: {
      status: 'danger',
    },
    onOk: async () => {
      try {
        await cancelSyncTask(task.task_id)
        Message.success('任务已取消')
        fetchTasks(false)
        fetchStats()
      } catch (error) {
        Message.error('取消任务失败')
        console.error(error)
      }
    },
  })
}

const fetchSchedule = async () => {
  try {
    const data = await getSyncSchedule()
    schedule.task_name = data.task_name
    schedule.enabled = data.enabled
    schedule.sync_time = data.sync_time
    schedule.sync_mode = data.sync_mode
    schedule.next_run_time = data.next_run_time
    schedule.updated_at = data.updated_at
  } catch (error) {
    console.error('获取定时同步配置失败:', error)
  }
}

const handleSaveSchedule = async () => {
  savingSchedule.value = true
  try {
    const data = await updateSyncSchedule({
      enabled: schedule.enabled,
      sync_time: schedule.sync_time,
      sync_mode: schedule.sync_mode,
    })
    schedule.task_name = data.task_name
    schedule.enabled = data.enabled
    schedule.sync_time = data.sync_time
    schedule.sync_mode = data.sync_mode
    schedule.next_run_time = data.next_run_time
    schedule.updated_at = data.updated_at
    Message.success('定时同步配置已保存')
  } catch (error) {
    Message.error('保存定时同步配置失败')
    console.error(error)
  } finally {
    savingSchedule.value = false
  }
}

// 自动刷新执行中的任务
let refreshTimer: number | null = null

const startAutoRefresh = () => {
  refreshTimer = window.setInterval(() => {
    const hasRunningTasks = tasks.value.some(
      (task) => task.status === 'running' || task.status === 'pending'
    )
    if (hasRunningTasks) {
      fetchTasks(false)
      fetchStats()
    }
  }, 2000)
}

const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onMounted(() => {
  fetchStats()
  fetchTasks()
  fetchSchedule()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.sync-logs-page {
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
  border: 1px solid var(--soft);
  box-shadow: var(--shadow-sm);
  transition: all 200ms ease;
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-label {
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 12px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--ink);
}

.stat-value.success {
  color: var(--green);
}

.stat-value.danger {
  color: var(--red);
}

.filter-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--soft);
  box-shadow: var(--shadow-sm);
  margin-bottom: 24px;
}

.schedule-card {
  background: white;
  padding: 20px 24px;
  border-radius: 16px;
  border: 1px solid var(--soft);
  box-shadow: var(--shadow-sm);
  margin-bottom: 24px;
}

.schedule-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}

.schedule-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
}

.schedule-desc {
  font-size: 12px;
  color: var(--muted);
}

.schedule-body {
  display: flex;
  align-items: center;
  gap: 32px;
  flex-wrap: wrap;
}

.schedule-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.schedule-label {
  font-size: 13px;
  color: var(--muted);
  white-space: nowrap;
}

.schedule-value {
  font-size: 13px;
  color: var(--ink);
}

.schedule-next {
  flex: 1;
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

.progress-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-cell :deep(.arco-progress) {
  flex: 1;
}

.progress-text {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
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
