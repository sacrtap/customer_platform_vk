<template>
  <div class="table-section">
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              :class="getThClass(col)"
              @click="col.sortable && toggleSort(col.key)"
            >
              <span>{{ col.title }}</span>
              <span v-if="col.sortable" class="th-sort-indicator"></span>
            </th>
            <th class="th-actions">操作</th>
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
            <td>
              <span class="cust-id">{{ record.company_id }}</span>
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
                <div class="balance-amount">
                  <b :class="{ danger: isNegativeBalance(record) }"
                    >¥{{ formatAmount(record.total_amount) }}</b
                  >
                  <span v-if="isNegativeBalance(record)" class="tag red">欠费</span>
                </div>
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
            <td>
              <span v-if="record.last_recharge_at">{{ formatDate(record.last_recharge_at) }}</span>
              <span v-else class="never-recharge">从未充值</span>
            </td>
            <td class="td-actions" @click.stop>
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
                重算
              </button>
            </td>
          </tr>
          <tr v-if="balances.length === 0 && !loading">
            <td :colspan="columns.length + 1" class="empty-state">暂无余额数据</td>
          </tr>
          <tr v-if="loading">
            <td :colspan="columns.length + 1" class="loading-state">加载中...</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <Pagination
      :current="pagination.current"
      :page-size="pagination.pageSize"
      :total="pagination.total"
      :page-size-options="pagination.pageSizeOptions"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { formatDate } from '@/utils/formatters'
import Pagination from '@/components/ui/Pagination.vue'
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
  can: (permission: string) => boolean
}

defineProps<Props>()

const emit = defineEmits<{
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

// --- 分页 ---
const onPageChange = (page: number) => {
  emit('pageChange', page)
}

const onPageSizeChange = (size: number) => {
  emit('pageSizeChange', size)
}

// --- 辅助方法 ---
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

// 负余额 = 欠费（后付费客户未回款或预付费客户透支），红色高亮并加「欠费」标签；
// 零余额客户数量大（多为未消耗客户），标红只会淹没真正的风险行，故保持中性。
const isNegativeBalance = (record: Balance): boolean => {
  return record.total_amount < 0
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
  padding: 8px 10px;
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
/* 操作列固定在右侧：表格宽度超出容器时按钮不会被裁出视口。
   sticky 单元格必须不透明，否则滚动内容会透出；行高亮用叠加背景还原底色。 */
.table th.th-actions,
.table td.td-actions {
  position: sticky;
  right: 0;
  white-space: nowrap;
  box-shadow: -8px 0 8px -8px rgba(15, 23, 42, 0.15);
}
.table th.th-actions {
  z-index: 3;
}
.table td.td-actions {
  z-index: 1;
  background: #fff;
}
.table tbody tr:hover td.td-actions {
  background: #f8fbff;
}
.table tbody tr.row-warning td.td-actions {
  background: linear-gradient(rgba(220, 38, 38, 0.04), rgba(220, 38, 38, 0.04)), #fff;
}
.table tbody tr.row-warn td.td-actions {
  background: linear-gradient(rgba(245, 158, 11, 0.04), rgba(245, 158, 11, 0.04)), #fff;
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
.balance-amount {
  display: flex;
  align-items: center;
  gap: 6px;
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

/* 从未充值 */
.never-recharge {
  color: var(--muted);
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
</style>
