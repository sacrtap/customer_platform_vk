<template>
  <div class="table-section">
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th style="width: 40px">
              <input
                type="checkbox"
                :checked="allChecked"
                :indeterminate.prop="someChecked"
                @change="toggleSelectAll"
              />
            </th>
            <th
              v-for="col in columns"
              :key="col.key"
              :class="getThClass(col)"
              @click="col.sortable && toggleSort(col.key)"
            >
              <span>{{ col.title }}</span>
              <span v-if="col.sortable" class="th-sort-indicator"></span>
            </th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="record in balances"
            :key="record.id"
            :class="{
              'row-warning': isBurningSoon(record),
              'row-warn': isBurningWarn(record),
            }"
          >
            <td @click.stop>
              <input
                type="checkbox"
                :checked="selectedIds.includes(record.customer_id)"
                @change="
                  emit('select', ($event.target as HTMLInputElement).checked, record.customer_id)
                "
              />
            </td>
            <td>
              <span class="cust-id">{{ record.company_id || record.customer_id }}</span>
            </td>
            <td>
              <div class="customer">
                <span class="logo">{{ getInitials(record.customer_name) }}</span>
                <b class="name-text">{{ record.customer_name || '-' }}</b>
              </div>
            </td>
            <td>{{ record.industry_type || '-' }}</td>
            <td>
              <div class="balance-info">
                <b :class="{ danger: isLowBalance(record) }"
                  >¥{{ formatAmount(record.total_amount) }}</b
                >
                <div class="balance-detail">
                  <span class="real">实：{{ formatAmount(record.real_amount) }}</span>
                  <span class="bonus">赠：{{ formatAmount(record.bonus_amount) }}</span>
                </div>
              </div>
            </td>
            <!-- 余额燃尽列：油表进度条 + 剩余天数 -->
            <td>
              <span v-if="record.settlement_type === 'postpaid'" class="tag gray">后付费</span>
              <div v-else class="burn-cell" :title="getBurnTooltip(record)">
                <div class="burn-bar" :class="getBurnBarClass(record)">
                  <div class="burn-fill" :style="{ width: getBurnFillPct(record) + '%' }"></div>
                </div>
                <span class="burn-text" :class="getBurnTextClass(record)">
                  {{ getBurnLabel(record) }}
                </span>
              </div>
            </td>
            <td>
              <div>
                <span>{{ formatAmount(record.used_total) }}</span>
                <div class="used-detail">
                  <span class="used-real">实：{{ formatAmount(record.used_real) }}</span>
                  <span class="used-bonus">赠：{{ formatAmount(record.used_bonus) }}</span>
                </div>
              </div>
            </td>
            <td>{{ record.last_recharge_at ? formatDate(record.last_recharge_at) : '-' }}</td>
            <td style="white-space: nowrap" @click.stop>
              <button
                v-if="can('billing:recharge')"
                class="btn"
                style="padding: 4px 10px; font-size: 12px"
                @click="emit('recharge', record)"
              >
                充值
              </button>
              <button
                class="btn"
                style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
                @click="emit('viewRecords', record)"
              >
                记录
              </button>
              <button
                v-if="can('billing:recharge')"
                class="btn btn-recalculate"
                style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
                @click="emit('recalculate', record)"
              >
                更新
              </button>
            </td>
          </tr>
          <tr v-if="balances.length === 0 && !loading">
            <td :colspan="columns.length + 2" class="empty-state">暂无余额数据</td>
          </tr>
          <tr v-if="loading">
            <td :colspan="columns.length + 2" class="loading-state">加载中...</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div class="pagination">
      <span class="page-total">共 {{ pagination.total.toLocaleString() }} 条</span>
      <div class="pagination-right">
        <span class="page-size">
          每页
          <select class="page-size-select" :value="pagination.pageSize" @change="onPageSizeChange">
            <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}</option>
          </select>
          条
        </span>
        <div class="page-controls">
          <button
            class="page-btn"
            :disabled="pagination.current <= 1"
            @click="onPageChange(pagination.current - 1)"
          >
            ‹
          </button>
          <button
            v-for="p in displayPages"
            :key="p"
            class="page-btn"
            :class="{ active: p === pagination.current, ellipsis: p === -1 }"
            :disabled="p === -1"
            @click="p > 0 && onPageChange(p)"
          >
            {{ p === -1 ? '…' : p }}
          </button>
          <button
            class="page-btn"
            :disabled="pagination.current >= totalPages"
            @click="onPageChange(pagination.current + 1)"
          >
            ›
          </button>
        </div>
        <span class="page-jump">
          跳至
          <input
            type="number"
            class="page-jump-input"
            :value="pagination.current"
            :min="1"
            :max="totalPages"
            @keydown.enter="onJumpPage(($event.target as HTMLInputElement).value)"
          />
          页
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { formatDate } from '@/utils/formatters'
import type { Balance } from '@/api/billing'

interface Props {
  balances: Balance[]
  loading: boolean
  pagination: {
    current: number
    pageSize: number
    total: number
    showTotal?: boolean
    showPageSize?: boolean
    showJumper?: boolean
    pageSizeOptions?: number[]
  }
  selectedIds: number[]
  can: (permission: string) => boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'select', checked: boolean, id: number): void
  (e: 'selectAll', checked: boolean): void
  (e: 'pageChange', page: number): void
  (e: 'pageSizeChange', pageSize: number): void
  (e: 'sortChange', dataIndex: string, direction: string): void
  (e: 'recharge', record: Balance): void
  (e: 'viewRecords', record: Balance): void
  (e: 'recalculate', record: Balance): void
}>()

// --- 列定义 ---
interface ColumnDef {
  key: string
  title: string
  sortable?: boolean
}

const columns: ColumnDef[] = [
  { key: 'company_id', title: '客户ID', sortable: true },
  { key: 'customer_name', title: '客户名称', sortable: true },
  { key: 'industry_type', title: '行业' },
  { key: 'total_amount', title: '余额', sortable: true },
  { key: 'burn_down', title: '余额燃尽', sortable: true },
  { key: 'used_total', title: '已消耗', sortable: true },
  { key: 'last_recharge_at', title: '最新充值', sortable: true },
]

// 前端列 key → 后端 sort_by 字段名映射
const sortFieldMap: Record<string, string> = {
  burn_down: 'days_remaining',
}

// --- 排序 ---
const sortKey = ref('')
const sortDir = ref<'asc' | 'desc' | ''>('')

const getThClass = (col: ColumnDef) => {
  if (!col.sortable) return ''
  const classes = ['th-sortable']
  if (sortKey.value === col.key) {
    if (sortDir.value === 'asc') classes.push('sort-asc')
    else if (sortDir.value === 'desc') classes.push('sort-desc')
  }
  return classes.join(' ')
}

const toggleSort = (key: string) => {
  if (sortKey.value === key) {
    if (sortDir.value === 'asc') sortDir.value = 'desc'
    else if (sortDir.value === 'desc') {
      sortKey.value = ''
      sortDir.value = ''
    } else sortDir.value = 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
  // 映射到后端字段名
  const backendField = sortFieldMap[sortKey.value] || sortKey.value
  emit('sortChange', backendField, sortDir.value)
}

// --- 选择 ---
const allChecked = computed(() => {
  return (
    props.balances.length > 0 &&
    props.balances.every((b) => props.selectedIds.includes(b.customer_id))
  )
})

const someChecked = computed(() => {
  return !allChecked.value && props.balances.some((b) => props.selectedIds.includes(b.customer_id))
})

const toggleSelectAll = (e: Event) => {
  emit('selectAll', (e.target as HTMLInputElement).checked)
}

// --- 分页 ---
const pageSizeOptions = props.pagination.pageSizeOptions || [10, 20, 50, 100]
const totalPages = computed(
  () => Math.ceil(props.pagination.total / props.pagination.pageSize) || 1
)

const displayPages = computed(() => {
  const current = props.pagination.current
  const total = totalPages.value
  const pages: number[] = []

  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i)
  } else {
    pages.push(1)
    if (current > 3) pages.push(-1)
    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)
    for (let i = start; i <= end; i++) pages.push(i)
    if (current < total - 2) pages.push(-1)
    pages.push(total)
  }
  return pages
})

const onPageChange = (page: number) => {
  if (page < 1 || page > totalPages.value) return
  emit('pageChange', page)
}

const onPageSizeChange = (e: Event) => {
  emit('pageSizeChange', Number((e.target as HTMLSelectElement).value))
}

const onJumpPage = (val: string) => {
  const page = parseInt(val)
  if (page >= 1 && page <= totalPages.value) {
    onPageChange(page)
  }
}

// --- 辅助方法 ---
const LOW_BALANCE_THRESHOLD = 10000
const BURN_MAX_DAYS = 60

const getInitials = (name?: string) => {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

const formatNumber = (num: number | null | undefined): string => {
  if (num == null) return '0'
  return num.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

const formatAmount = (num: number | null | undefined): string => {
  if (num == null) return '0.00'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const isLowBalance = (record: Balance): boolean => {
  // 余额 ≤ 0（欠费）或低于阈值时显示红色
  return (
    record.total_amount <= 0 ||
    (record.total_amount > 0 && record.total_amount < LOW_BALANCE_THRESHOLD)
  )
}

// ===== 余额燃尽：油表进度条（满 = 安全，空 = 紧急）=====

// 行高亮：≤7 天红色背景
const isBurningSoon = (record: Balance): boolean => {
  return record.days_remaining != null && record.days_remaining <= 7
}

// 行高亮：8-30 天浅黄色背景
const isBurningWarn = (record: Balance): boolean => {
  return record.days_remaining != null && record.days_remaining > 7 && record.days_remaining <= 30
}

// 进度条填充百分比：满格 = 安全（剩余天数多），空 = 紧急
const getBurnFillPct = (record: Balance): number => {
  if (record.days_remaining == null) return 100 // 无消耗 → 满格灰色
  if (record.days_remaining <= 0) return 0 // 已耗尽 → 空格红色
  return Math.min((record.days_remaining / BURN_MAX_DAYS) * 100, 100)
}

// 进度条颜色 class
const getBurnBarClass = (record: Balance): string => {
  if (record.settlement_type === 'postpaid') return 'postpaid'
  if (record.days_remaining == null) return 'no-data'
  if (record.days_remaining <= 0) return 'danger'
  if (record.days_remaining <= 7) return 'danger'
  if (record.days_remaining <= 30) return 'warn'
  // 数据覆盖率 <50%（30天中 <15天有记录）→ 颜色降级
  if (record.consumption_days > 0 && record.consumption_days < 15) return 'warn'
  return 'safe'
}

// 文字颜色 class（与进度条一致）
const getBurnTextClass = (record: Balance): string => {
  return getBurnBarClass(record)
}

// 核心文字标签
const getBurnLabel = (record: Balance): string => {
  if (record.days_remaining == null) return '无消耗'
  if (record.days_remaining <= 0) return '已耗尽'
  if (record.days_remaining < 1) return '今日耗尽'
  if (record.days_remaining > BURN_MAX_DAYS) return '>60天'
  return `剩余 ${Math.floor(record.days_remaining)}天`
}

// tooltip 详情
const getBurnTooltip = (record: Balance): string => {
  if (record.settlement_type === 'postpaid') return '后付费客户，不消耗预付余额'
  if (record.days_remaining == null) {
    const parts = ['近 30 天无消费记录']
    if (record.last_recharge_at) {
      const lastDate = new Date(record.last_recharge_at)
      const now = new Date()
      const daysSince = Math.floor((now.getTime() - lastDate.getTime()) / (1000 * 60 * 60 * 24))
      parts.push(`距上次充值 ${daysSince} 天`)
    }
    return parts.join('；')
  }

  const parts: string[] = []
  if (record.daily_avg_cost != null) {
    parts.push(`日均消耗 ¥${formatNumber(record.daily_avg_cost)}`)
  }
  parts.push(`30 天内有 ${record.consumption_days} 天消费记录`)

  const remaining = record.real_amount + record.bonus_amount
  parts.push(`当前余额 ¥${formatNumber(remaining)}`)

  if (record.days_remaining <= 0) {
    parts.push('余额已耗尽，需立即充值')
  } else if (record.days_remaining < 1) {
    parts.push('今日即将耗尽')
  } else {
    parts.push(`预计可支撑 ${Math.floor(record.days_remaining)} 天`)
  }

  // 数据覆盖率提示
  if (record.consumption_days > 0 && record.consumption_days < 15) {
    parts.push('⚠️ 消费数据覆盖率较低，预测可能不准确')
  }

  parts.push('预测基于近 30 天日均消耗，实际扣款以结算单为准')
  return parts.join('；')
}
</script>

<style scoped>
.table-section {
  display: flex;
  flex-direction: column;
}

/* 表格容器 */
.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 15px;
}

/* 表格 */
.table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  table-layout: auto;
}
.table th,
.table td {
  padding: 10px 10px;
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  white-space: nowrap;
}
.table th {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
}
.table tbody tr {
  transition: background 0.15s;
}
.table tbody tr:hover td {
  background: #f8fbff;
}

/* 行高亮：即将耗尽（≤7天）红色 */
.table tbody tr.row-warning td {
  background: rgba(220, 38, 38, 0.04);
}
.table tbody tr.row-warning:hover td {
  background: rgba(220, 38, 38, 0.07);
}

/* 行高亮：余额偏低（8-30天）浅黄色 */
.table tbody tr.row-warn td {
  background: rgba(245, 158, 11, 0.04);
}
.table tbody tr.row-warn:hover td {
  background: rgba(245, 158, 11, 0.07);
}
/* row-warning 优先级高于 row-warn */
.table tbody tr.row-warning.row-warn td {
  background: rgba(220, 38, 38, 0.04);
}

/* 客户ID */
.cust-id {
  font-variant-numeric: tabular-nums;
  color: var(--muted);
  font-size: 13px;
}

/* 客户名称单元格 */
.customer {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 200px;
}
.customer .logo {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #e0f2fe;
  color: #0369a1;
  display: grid;
  place-items: center;
  font-weight: 850;
  font-size: 12px;
  flex-shrink: 0;
}
.customer .name-text {
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subtle {
  color: var(--muted);
  font-size: 12px;
}

/* 标签 */
.tag {
  display: inline-flex;
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.tag.blue {
  background: #dbeafe;
  color: #1d4ed8;
}
.tag.green {
  background: #dcfce7;
  color: #047857;
}
.tag.amber {
  background: #fef3c7;
  color: #b45309;
}
.tag.red {
  background: #fee2e2;
  color: #b91c1c;
}
.tag.gray {
  background: #f1f5f9;
  color: #475569;
}

/* 余额信息 */
.balance-info {
  display: flex;
  flex-direction: column;
}
.balance-info b {
  font-weight: 700;
  color: var(--ink);
}
.balance-info b.danger {
  color: #dc2626;
}
.balance-detail {
  font-size: 11px;
  color: var(--muted);
  margin-top: 2px;
  display: flex;
  gap: 12px;
}
.balance-detail .real {
  color: var(--primary);
}
.balance-detail .bonus {
  color: var(--green, #059669);
}

/* 余额燃尽列：油表进度条 */
.burn-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 110px;
  cursor: help;
}
.burn-bar {
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  overflow: hidden;
}
.burn-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}
.burn-bar.safe .burn-fill {
  background: #10b981;
}
.burn-bar.warn .burn-fill {
  background: #f59e0b;
}
.burn-bar.danger .burn-fill {
  background: #ef4444;
}
.burn-bar.no-data .burn-fill {
  background: #cbd5e1;
}
.burn-bar.postpaid {
  display: none;
}

/* 燃尽文字 */
.burn-text {
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.burn-text.safe {
  color: #059669;
}
.burn-text.warn {
  color: #d97706;
}
.burn-text.danger {
  color: #dc2626;
}
.burn-text.no-data {
  color: var(--muted);
}

/* 已消耗 */
.used-detail {
  font-size: 11px;
  color: var(--muted);
  margin-top: 2px;
  display: flex;
  gap: 12px;
}
.used-detail .used-real {
  color: #dc2626;
}
.used-detail .used-bonus {
  color: var(--muted);
}

/* 排序表头 */
.th-sortable {
  cursor: pointer;
  user-select: none;
  position: relative;
  padding-right: 20px !important;
}
.th-sortable:hover {
  color: var(--primary);
}
.th-sort-indicator {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 10px;
  color: var(--muted);
  line-height: 1;
}
.th-sortable.sort-asc .th-sort-indicator {
  color: var(--primary);
}
.th-sortable.sort-desc .th-sort-indicator {
  color: var(--primary);
}
.th-sortable.sort-asc .th-sort-indicator::after {
  content: '▲';
}
.th-sortable.sort-desc .th-sort-indicator::after {
  content: '▼';
}
.th-sortable:not(.sort-asc):not(.sort-desc) .th-sort-indicator::after {
  content: '⇅';
  opacity: 0.4;
}

/* 按钮 */
.btn {
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  border-radius: 12px;
  padding: 9px 12px;
  cursor: pointer;
  font-weight: 700;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}
.btn:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.btn-recalculate {
  color: #6366f1;
  border-color: #c7d2fe;
}
.btn-recalculate:hover {
  border-color: #6366f1;
  background: #eef2ff;
  color: #4338ca;
}

/* 空状态 */
.empty-state,
.loading-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--muted);
  font-size: 14px;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #edf2f7;
}
.page-total {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.pagination-right {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: auto;
}
.page-size {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}
.page-size-select {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 3px 6px;
  font: inherit;
  font-size: 12px;
  color: var(--ink);
  background: #fff;
  cursor: pointer;
}
.page-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}
.page-btn {
  min-width: 32px;
  height: 32px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  border-radius: 8px;
  padding: 0 8px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.page-btn:hover:not(:disabled):not(.active) {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}
.page-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  cursor: default;
}
.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-btn.ellipsis {
  border: none;
  background: transparent;
  cursor: default;
  opacity: 1;
}
.page-jump {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}
.page-jump-input {
  width: 48px;
  height: 30px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0 6px;
  font: inherit;
  font-size: 12px;
  text-align: center;
  color: var(--ink);
  background: #fff;
}
.page-jump-input:focus {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 2px rgba(147, 197, 253, 0.2);
}

@media (max-width: 640px) {
  .pagination {
    justify-content: center;
  }
  .page-size,
  .page-jump {
    display: none;
  }
}
</style>
