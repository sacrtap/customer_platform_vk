<template>
  <a-drawer
    :visible="visible"
    title="执行信息"
    width="900px"
    unmount-on-close
    :footer="false"
    @cancel="handleClose"
  >
    <template v-if="task">
      <!-- 任务概览 -->
      <div class="task-overview">
        <div class="overview-title">
          <span class="task-id">任务 {{ shortTaskId }}</span>
          <a-tag :color="getStatusColor(task.status)">{{ getStatusText(task.status) }}</a-tag>
        </div>
        <div class="overview-meta">
          <span>周期：{{ task.start_date }} ~ {{ task.end_date }}</span>
          <span>模式：{{ task.sync_mode === 'skip_existing' ? '仅同步无数据' : '强制覆盖' }}</span>
          <span v-if="task.operator_name">操作人：{{ task.operator_name }}</span>
          <span v-else-if="task.operator_id == null">操作人：系统自动</span>
        </div>

        <!-- 统计概览 -->
        <div class="overview-stats">
          <div class="stat-item">
            <div class="stat-value success">{{ summary.info_count ?? task.info_count ?? 0 }}</div>
            <div class="stat-label">成功记录数</div>
          </div>
          <div class="stat-item">
            <div class="stat-value warning">
              {{ summary.warning_count ?? task.warning_count ?? 0 }}
            </div>
            <div class="stat-label">警告数</div>
          </div>
          <div class="stat-item">
            <div class="stat-value danger">{{ summary.error_count ?? task.error_count ?? 0 }}</div>
            <div class="stat-label">错误数</div>
          </div>
        </div>
      </div>

      <!-- 级别过滤 -->
      <div class="filter-bar">
        <a-radio-group
          v-model="filterLevel"
          type="button"
          size="small"
          @change="handleFilterChange"
        >
          <a-radio value="">全部</a-radio>
          <a-radio value="warning">警告</a-radio>
          <a-radio value="error">错误</a-radio>
          <a-radio value="info">成功</a-radio>
        </a-radio-group>
      </div>

      <!-- 明细表格 -->
      <a-table
        :columns="columns"
        :data="details"
        :loading="loading"
        :pagination="pagination"
        size="small"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #level="{ record }">
          <a-tag :color="levelColor(record.level)">{{ levelText(record.level) }}</a-tag>
        </template>
        <template #category="{ record }">
          {{ categoryText(record.category) }}
        </template>
        <template #message="{ record }">
          <a-tooltip :content="record.message">
            <span class="message-cell">{{ record.message }}</span>
          </a-tooltip>
        </template>
        <template #customer="{ record }">
          <span v-if="record.customer_id">
            {{ record.customer_id
            }}<span v-if="record.customer_name"> · {{ record.customer_name }}</span>
          </span>
          <span v-else-if="record.external_customer_id || record.company_name">-</span>
          <span v-else>-</span>
        </template>
        <template #external="{ record }">
          <span v-if="record.external_customer_id">{{ record.external_customer_id }}</span>
          <span v-else>-</span>
        </template>
        <template #company="{ record }">
          <span v-if="record.company_name">{{ record.company_name }}</span>
          <span v-else>-</span>
        </template>
        <template #order_code="{ record }">
          <span v-if="record.order_code">{{ record.order_code }}</span>
          <span v-else>-</span>
        </template>
        <template #record_count="{ record }">
          <span v-if="record.record_count > 1">{{ record.record_count }}</span>
          <span v-else>-</span>
        </template>
      </a-table>

      <div v-if="!loading && summary.total_count === 0" class="empty-tip">
        该任务无执行明细记录（历史任务）
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { getSyncTaskDetails, type SyncLogDetail, type SyncTask } from '@/api/syncTasks'

const props = defineProps<{
  visible: boolean
  task: SyncTask | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const loading = ref(false)
const details = ref<SyncLogDetail[]>([])
const filterLevel = ref('')

const summary = reactive({
  info_count: 0,
  warning_count: 0,
  error_count: 0,
  total_count: 0,
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const shortTaskId = computed(() => (props.task ? props.task.task_id.substring(0, 8) : ''))

const columns = [
  { title: '级别', slotName: 'level', width: 80 },
  { title: '日期', dataIndex: 'sync_date', width: 110 },
  { title: '类别', slotName: 'category', width: 90 },
  { title: '客户ID · 名称', slotName: 'customer', width: 180 },
  { title: '外部客户ID', slotName: 'external', width: 90 },
  { title: '公司名', slotName: 'company', width: 140 },
  { title: '订单号', slotName: 'order_code', width: 140 },
  { title: '记录数', slotName: 'record_count', width: 70 },
  { title: '信息', slotName: 'message' },
]

const levelColor = (level: string) => {
  if (level === 'error') return 'red'
  if (level === 'warning') return 'gold'
  return 'green'
}

const levelText = (level: string) => {
  if (level === 'error') return '错误'
  if (level === 'warning') return '警告'
  return '成功'
}

const categoryText = (category: string) => {
  const map: Record<string, string> = {
    order_fetch: '拉取订单',
    order_match: '订单匹配',
    order_save: '订单保存',
    cost_calc: '费用计算',
    data_check: '数据校验',
    system: '任务级',
  }
  return map[category] || category
}

const getStatusColor = (status: string) => {
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

const fetchDetails = async () => {
  if (!props.task) return
  loading.value = true
  try {
    const data = await getSyncTaskDetails(props.task.task_id, {
      level: filterLevel.value || undefined,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    details.value = data.list
    summary.info_count = data.summary.info_count
    summary.warning_count = data.summary.warning_count
    summary.error_count = data.summary.error_count
    summary.total_count = data.summary.total_count
    pagination.total = data.pagination.total
  } catch (error) {
    console.error('获取执行明细失败:', error)
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => {
  pagination.current = 1
  fetchDetails()
}

const handlePageChange = (page: number) => {
  pagination.current = page
  fetchDetails()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchDetails()
}

const handleClose = () => {
  emit('update:visible', false)
}

watch(
  () => props.visible,
  (visible) => {
    if (visible && props.task) {
      filterLevel.value = ''
      pagination.current = 1
      fetchDetails()
    }
  }
)
</script>

<style scoped>
.task-overview {
  margin-bottom: 16px;
}

.overview-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.task-id {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}

.overview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 16px;
}

.overview-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.stat-item {
  background: #fafafa;
  border: 1px solid var(--soft);
  border-radius: 8px;
  padding: 12px 16px;
  text-align: center;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
}

.stat-value.success {
  color: var(--green);
}

.stat-value.warning {
  color: #d97706;
}

.stat-value.danger {
  color: var(--red);
}

.stat-label {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
}

.filter-bar {
  margin: 16px 0 12px;
}

.message-cell {
  display: block;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-tip {
  text-align: center;
  color: var(--muted);
  padding: 32px 0;
  font-size: 13px;
}
</style>
