<template>
  <a-drawer
    v-model:visible="isVisible"
    title="明细文件生成状态"
    width="760px"
    unmount-on-close
    :footer="false"
  >
    <div class="detail-gen-drawer">
      <!-- 状态筛选 tabs（counts 作 badge） -->
      <a-tabs v-model:active-key="statusFilter" type="capsule" @change="onTabChange">
        <a-tab-pane key="all" title="全部" />
        <a-tab-pane key="pending">
          <template #title>
            待生成<a-tag v-if="counts.pending" size="small" color="orange">{{
              counts.pending
            }}</a-tag>
          </template>
        </a-tab-pane>
        <a-tab-pane key="generating">
          <template #title>
            生成中<a-tag v-if="counts.generating" size="small" color="blue">{{
              counts.generating
            }}</a-tag>
          </template>
        </a-tab-pane>
        <a-tab-pane key="failed">
          <template #title>
            失败<a-tag v-if="counts.failed" size="small" color="red">{{ counts.failed }}</a-tag>
          </template>
        </a-tab-pane>
        <a-tab-pane key="completed">
          <template #title>
            已完成<a-tag v-if="counts.completed" size="small" color="green">{{
              counts.completed
            }}</a-tag>
          </template>
        </a-tab-pane>
      </a-tabs>

      <!-- 列表 -->
      <a-table
        :columns="columns"
        :data="rows"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="small"
      >
        <template #status="{ record }">
          <a-tag :color="statusColor(record.detail_file_status)">{{
            statusText(record.detail_file_status)
          }}</a-tag>
        </template>
        <template #period="{ record }">
          <span class="cell-nowrap"
            >{{ formatDate(record.period_start) }} ~ {{ formatDate(record.period_end) }}</span
          >
        </template>
        <template #updated_at="{ record }">
          <span class="cell-nowrap">{{ formatDateTime(record.updated_at) }}</span>
        </template>
        <template #operations="{ record }">
          <a-button
            v-if="canRegenerate(record) && can('billing:edit')"
            type="text"
            size="mini"
            @click="onRegenerate([record.id])"
          >
            重新生成
          </a-button>
          <span v-else class="subtle">—</span>
        </template>
      </a-table>

      <!-- 分页 -->
      <div class="pagination-row">
        <a-pagination
          :current="page"
          :page-size="pageSize"
          :total="total"
          size="small"
          show-total
          @change="onPageChange"
        />
      </div>

      <!-- 底部批量操作 -->
      <div class="footer-actions">
        <span class="subtle">提示：重新生成会重置为待处理并异步执行，可刷新查看最新状态。</span>
        <a-button
          v-if="can('billing:edit')"
          type="primary"
          size="small"
          :disabled="counts.failed + counts.pending === 0"
          @click="onRegeneratePendingOrFailed"
        >
          批量重新生成待生成/失败项（{{ counts.failed + counts.pending }}）
        </a-button>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getInvoiceDetailLogs, regenerateDetailBatch } from '@/api/billing'
import type { DetailFileStatus } from '@/api/billing'
import { formatDate, formatDateTime } from '@/utils/formatters'
import { useUserStore } from '@/stores/user'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  regenerated: []
}>()

const userStore = useUserStore()
const can = (p: string) => userStore.hasPermission(p)

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

interface DetailLogRow {
  id: number
  invoice_no: string
  customer_name: string | null
  period_start: string | null
  period_end: string | null
  detail_file_status: DetailFileStatus | null
  updated_at: string | null
}

interface DetailLogCounts {
  pending: number
  generating: number
  completed: number
  failed: number
}

const loading = ref(false)
const rows = ref<DetailLogRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('all')
const counts = reactive<DetailLogCounts>({ pending: 0, generating: 0, completed: 0, failed: 0 })

const columns = [
  { title: '结算单号', dataIndex: 'invoice_no', width: 180 },
  { title: '客户', dataIndex: 'customer_name', ellipsis: true },
  { title: '周期', slotName: 'period', width: 200 },
  { title: '状态', slotName: 'status', width: 90 },
  { title: '更新时间', slotName: 'updated_at', width: 170 },
  { title: '操作', slotName: 'operations', width: 100 },
]

const STATUS_TEXT: Record<DetailFileStatus, string> = {
  pending: '待生成',
  generating: '生成中',
  completed: '已完成',
  failed: '失败',
}

const STATUS_COLOR: Record<DetailFileStatus, string> = {
  pending: 'orange',
  generating: 'blue',
  completed: 'green',
  failed: 'red',
}

const statusText = (status: DetailFileStatus | null) => STATUS_TEXT[status || 'pending']
const statusColor = (status: DetailFileStatus | null) => STATUS_COLOR[status || 'pending']

// 失败与长期卡在 pending 的行都允许手动重试（pending 卡住多为任务丢失，见 route 注释）
const canRegenerate = (record: DetailLogRow) =>
  record.detail_file_status === 'failed' || record.detail_file_status === 'pending'

const loadData = async () => {
  loading.value = true
  try {
    const res = await getInvoiceDetailLogs({
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = res.data?.list || []
    total.value = res.data?.total || 0
    if (res.data?.counts) {
      counts.pending = res.data.counts.pending || 0
      counts.generating = res.data.counts.generating || 0
      counts.completed = res.data.counts.completed || 0
      counts.failed = res.data.counts.failed || 0
    }
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const onTabChange = () => {
  page.value = 1
  loadData()
}

const onPageChange = (p: number) => {
  page.value = p
  loadData()
}

const onRegenerate = async (ids: number[]) => {
  try {
    const res = await regenerateDetailBatch(ids)
    const data = res.data
    Message.success(
      `已触发 ${data?.triggered ?? 0} 个重新生成${data?.failed?.length ? `，失败 ${data.failed.length} 个` : ''}`
    )
    emit('regenerated')
    loadData()
  } catch {
    Message.error('重新生成失败')
  }
}

const onRegeneratePendingOrFailed = async () => {
  await onRegenerate(
    rows.value
      .filter((r) => r.detail_file_status === 'failed' || r.detail_file_status === 'pending')
      .map((r) => r.id)
  )
}

// 抽屉打开时加载；轮询生成中的状态（复用 getInvoiceDetailLogs 刷新）
watch(
  () => props.visible,
  (val) => {
    if (val) {
      page.value = 1
      loadData()
    }
  }
)

// 生成中存在时定时刷新列表
// 轮询条件覆盖 pending：任务排队中/被 misfire 丢弃的单停在 pending，
// 只轮 generating 会让这些单的状态永远不刷新（用户看到"待生成"卡住不动）。
let pollTimer: ReturnType<typeof setInterval> | null = null
const needsPolling = () => counts.generating > 0 || counts.pending > 0

watch(
  () => props.visible,
  (val) => {
    if (val) {
      pollTimer = setInterval(() => {
        if (needsPolling()) loadData()
      }, 5000)
    } else if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }
)

// 抽屉在打开状态下被卸载（路由切换等）时清理定时器，防止泄漏
onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped>
.detail-gen-drawer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.pagination-row {
  display: flex;
  justify-content: flex-end;
}
.footer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
}
.footer-actions .subtle {
  font-size: 12px;
}
.cell-nowrap {
  white-space: nowrap;
}
</style>
