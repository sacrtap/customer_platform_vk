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
          <span v-else-if="task.operator_id === null || task.operator_id === undefined"
            >操作人：系统自动</span
          >
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

      <!-- 筛选区（类型/是否结算/公司ID名称搜索） -->
      <div class="filter-section">
        <a-form layout="inline">
          <a-form-item label="类型">
            <a-select v-model="filterType" style="width: 130px" @change="handleFilterChange">
              <a-option value="">全部</a-option>
              <a-option value="cost">费用计算</a-option>
              <a-option value="order">订单匹配</a-option>
            </a-select>
          </a-form-item>
          <a-form-item label="是否结算">
            <a-select v-model="filterIsSettled" style="width: 110px" @change="handleFilterChange">
              <a-option value="all">全部</a-option>
              <a-option value="true">是</a-option>
              <a-option value="false">否</a-option>
            </a-select>
          </a-form-item>
          <a-form-item label="账号类型">
            <a-select
              v-model="filterAccountType"
              style="width: 130px"
              allow-clear
              @change="handleFilterChange"
            >
              <a-option value="">全部</a-option>
              <a-option v-for="opt in ACCOUNT_TYPE_OPTIONS" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item label="公司ID/名称">
            <a-input
              v-model="filterKeyword"
              placeholder="公司ID 或名称"
              style="width: 180px"
              allow-clear
              @press-enter="handleFilterChange"
            />
          </a-form-item>
          <a-form-item>
            <a-space>
              <a-button type="primary" size="small" @click="handleFilterChange">查询</a-button>
              <a-button size="small" @click="handleResetFilters">重置</a-button>
            </a-space>
          </a-form-item>
        </a-form>
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
        :data="displayDetails"
        :loading="loading"
        :pagination="pagination"
        size="small"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #sync_date="{ record }">
          <span>{{ record.sync_date }}</span>
        </template>
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
          <span v-if="record.company_id ?? record.external_customer_id ?? record.customer_name">
            {{ record.company_id ?? record.external_customer_id ?? '-' }}
            <template v-if="record.customer_name"> · {{ record.customer_name }}</template>
          </span>
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
        <template #is_settled="{ record }">
          <span v-if="record.is_settlement_enabled === true">是</span>
          <span v-else-if="record.is_settlement_enabled === false">否</span>
          <span v-else>-</span>
        </template>
        <template #account_type="{ record }">
          <span v-if="record.account_type">{{ record.account_type }}</span>
          <span v-else>-</span>
        </template>
        <template #record_count="{ record }">
          <span v-if="record._isDateGroupLast" class="subtotal">{{ record._dateSubtotal }}</span>
          <span v-else-if="record.record_count > 1">{{ record.record_count }}</span>
          <span v-else>-</span>
        </template>
      </a-table>

      <div v-if="loadError && !loading" class="empty-tip error">加载执行明细失败，请稍后重试</div>
      <div v-else-if="!loading && summary.total_count === 0" class="empty-tip">
        <template v-if="task.error_message">
          <div class="empty-title">该任务无执行明细记录（历史任务）</div>
          <div class="empty-error">任务错误信息：{{ task.error_message }}</div>
        </template>
        <template v-else>该任务无执行明细记录（历史任务）</template>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { getSyncTaskDetails, type SyncLogDetail, type SyncTask } from '@/api/syncTasks'
import { ACCOUNT_TYPE_OPTIONS } from '@/constants/customerOptions'

const props = defineProps<{
  visible: boolean
  task: SyncTask | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const loading = ref(false)
const loadError = ref(false)
const details = ref<SyncLogDetail[]>([])
const filterLevel = ref('')
const filterType = ref('')
const filterIsSettled = ref('true')
const filterKeyword = ref('')
const filterAccountType = ref('')

const summary = reactive({
  info_count: null as number | null,
  warning_count: null as number | null,
  error_count: null as number | null,
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

interface DisplayDetail extends SyncLogDetail {
  _isDateGroupLast: boolean
  _dateSubtotal: number
}

// 按 sync_date 分组：组首标记 + 当日记录数小计（基于当前页）
const displayDetails = computed<DisplayDetail[]>(() => {
  const list = details.value
  const totals = new Map<string, number>()
  const counts = new Map<string, number>()
  for (const d of list) {
    totals.set(d.sync_date, (totals.get(d.sync_date) ?? 0) + d.record_count)
    counts.set(d.sync_date, (counts.get(d.sync_date) ?? 0) + 1)
  }
  const seen = new Map<string, number>()
  return list.map((d) => {
    const idx = seen.get(d.sync_date) ?? 0
    seen.set(d.sync_date, idx + 1)
    return {
      ...d,
      _isDateGroupLast: idx === (counts.get(d.sync_date) ?? 1) - 1,
      _dateSubtotal: totals.get(d.sync_date) ?? d.record_count,
    }
  })
})

const columns = [
  { title: '级别', slotName: 'level', width: 80 },
  { title: '日期', slotName: 'sync_date', width: 140 },
  { title: '类别', slotName: 'category', width: 90 },
  { title: '公司ID · 名称', slotName: 'customer', width: 180 },
  { title: '公司名', slotName: 'company', width: 140 },
  { title: '订单号', slotName: 'order_code', width: 140 },
  { title: '是否结算', slotName: 'is_settled', width: 90 },
  { title: '账号类型', slotName: 'account_type', width: 110 },
  { title: '记录数', slotName: 'record_count', width: 90 },
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
  loadError.value = false
  try {
    const data = await getSyncTaskDetails(props.task.task_id, {
      level: filterLevel.value || undefined,
      type: filterType.value || undefined,
      is_settled: filterIsSettled.value || undefined,
      keyword: filterKeyword.value || undefined,
      account_type: filterAccountType.value || undefined,
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
    loadError.value = true
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => {
  pagination.current = 1
  fetchDetails()
}

const handleResetFilters = () => {
  filterType.value = ''
  filterIsSettled.value = 'true'
  filterKeyword.value = ''
  filterAccountType.value = ''
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
  () => [props.visible, props.task?.task_id],
  ([visible]) => {
    if (visible && props.task) {
      filterLevel.value = ''
      filterType.value = ''
      filterIsSettled.value = 'true'
      filterKeyword.value = ''
      filterAccountType.value = ''
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

.filter-section {
  margin: 16px 0 0;
}

.filter-bar {
  margin: 16px 0 12px;
}

.subtotal {
  color: var(--muted);
  font-weight: 600;
  white-space: nowrap;
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
