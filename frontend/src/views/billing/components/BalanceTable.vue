<template>
  <DataTable
    :columns="tableColumns"
    :data="balances as unknown as Record<string, unknown>[]"
    :loading="loading"
    :pagination="paginationConfig"
    :row-key="'id'"
    :row-class="rowClassFn"
    :scroll="{ x: 1050 }"
    :storage-key="STORAGE_KEY"
    @page-change="onPageChange"
    @page-size-change="onPageSizeChange"
    @sorter-change="onSorterChange"
  >
    <template #company_id="{ record }">
      <span class="cust-id">{{ (record as Balance).company_id }}</span>
    </template>

    <template #customer_name="{ record }">
      <div class="customer">
        <span class="logo">{{ getInitials((record as Balance).customer_name) }}</span>
        <b class="name-text">{{ (record as Balance).customer_name || '-' }}</b>
      </div>
    </template>

    <template #industry_type="{ record }">
      {{ (record as Balance).industry_type || '-' }}
    </template>

    <template #total_amount="{ record }">
      <!-- 非包年：实收/赠送拆分 -->
      <div v-if="!(record as Balance).is_package" class="balance-info">
        <div class="balance-amount">
          <b :class="{ danger: isNegativeBalance(record as Balance) }"
            >¥{{ formatAmount((record as Balance).total_amount) }}</b
          >
          <span v-if="isNegativeBalance(record as Balance)" class="tag red">欠费</span>
        </div>
        <div class="balance-detail">
          <span class="real">实：{{ formatAmount((record as Balance).real_amount) }}</span>
          <span class="bonus">赠：{{ formatAmount((record as Balance).bonus_amount) }}</span>
        </div>
      </div>
      <!-- 包年客户：套餐剩余额度 + 剩余次数（不限量显示「不限量」） -->
      <div v-else class="balance-info">
        <div class="balance-amount">
          <b :class="{ danger: (record as Balance).package_expired }"
            >¥{{ formatAmount((record as Balance).package_remaining_amount) }}</b
          >
          <span v-if="(record as Balance).package_expired" class="tag gray">套餐已过期</span>
          <span v-else-if="(record as Balance).package_is_unlimited" class="tag blue">不限量</span>
        </div>
        <div class="balance-detail">
          <span class="real"
            >额度：¥{{ formatAmount((record as Balance).package_remaining_amount) }}</span
          >
          <span
            v-if="
              !(record as Balance).package_is_unlimited &&
              (record as Balance).package_remaining_count != null
            "
            class="bonus"
            >次数：{{ formatCount((record as Balance).package_remaining_count) }}</span
          >
        </div>
      </div>
    </template>

    <template #burn_down="{ record }">
      <span v-if="(record as Balance).settlement_type === 'postpaid'" class="tag gray">后付费</span>
      <span v-else-if="(record as Balance).package_expired" class="tag gray">套餐已过期</span>
      <a-tooltip
        v-else-if="(record as Balance).is_package"
        :content="getPackageBurnTooltip(record as Balance)"
      >
        <div class="burn-cell">
          <div class="burn-bar" :class="getPackageBurnBarClass(record as Balance)">
            <div
              class="burn-fill"
              :style="{ width: getPackageBurnFillPct(record as Balance) + '%' }"
            ></div>
          </div>
          <span class="burn-text" :class="getPackageBurnBarClass(record as Balance)">
            {{ getPackageBurnLabel(record as Balance) }}
          </span>
        </div>
      </a-tooltip>
      <a-tooltip v-else :content="getBurnTooltip(record as Balance)">
        <div class="burn-cell">
          <div class="burn-bar" :class="getBurnBarClass(record as Balance)">
            <div
              class="burn-fill"
              :style="{ width: getBurnFillPct(record as Balance) + '%' }"
            ></div>
          </div>
          <span class="burn-text" :class="getBurnTextClass(record as Balance)">
            {{ getBurnLabel(record as Balance) }}
          </span>
        </div>
      </a-tooltip>
    </template>

    <template #used_total="{ record }">
      <!-- 包年客户：「已消耗」= 套餐内累计消耗（实时，含未结算），与余额列同口径 -->
      <a-tooltip
        v-if="(record as Balance).is_package && (record as Balance).package_consumed_amount != null"
        :content="getPackageConsumedTooltip(record as Balance)"
      >
        <div>
          <span>{{ formatAmount((record as Balance).package_consumed_amount) }}</span>
          <div class="used-detail">
            <span class="used-package">套餐内累计消耗（实时）</span>
          </div>
        </div>
      </a-tooltip>
      <div v-else>
        <span>{{ formatAmount((record as Balance).used_total) }}</span>
        <div class="used-detail">
          <span class="used-real">实：{{ formatAmount((record as Balance).used_real) }}</span>
          <span class="used-bonus">赠：{{ formatAmount((record as Balance).used_bonus) }}</span>
        </div>
      </div>
    </template>

    <template #last_recharge_at="{ record }">
      <span v-if="(record as Balance).last_recharge_at">{{
        formatDate((record as Balance).last_recharge_at!)
      }}</span>
      <span v-else class="never-recharge">从未充值</span>
    </template>

    <template #action="{ record }">
      <button
        v-if="can('billing:recharge')"
        class="btn"
        style="padding: 4px 10px; font-size: 12px"
        @click.stop="emit('recharge', record as Balance)"
      >
        充值
      </button>
      <button
        class="btn"
        style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
        @click.stop="emit('viewRecords', record as Balance)"
      >
        记录
      </button>
      <button
        v-if="can('billing:recharge')"
        class="btn btn-recalculate"
        style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
        @click.stop="emit('recalculate', record as Balance)"
      >
        重算
      </button>
    </template>
  </DataTable>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatDate } from '@/utils/formatters'
import DataTable, { type DataTableColumn } from '@/components/DataTable.vue'
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

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'pageChange', page: number): void
  (e: 'pageSizeChange', pageSize: number): void
  (e: 'sortChange', dataIndex: string, direction: string): void
  (e: 'recharge', record: Balance): void
  (e: 'viewRecords', record: Balance): void
  (e: 'recalculate', record: Balance): void
}>()

// --- 列定义（原 columns + 操作列固定右侧） ---
interface ColumnDef {
  key: string
  title: string
  sortable?: boolean
  width?: number
}

const columnDefs: ColumnDef[] = [
  { key: 'company_id', title: '客户ID', sortable: true, width: 64 },
  { key: 'customer_name', title: '客户名称', sortable: true, width: 200 },
  { key: 'industry_type', title: '行业', width: 100 },
  { key: 'total_amount', title: '余额', sortable: true, width: 138 },
  { key: 'burn_down', title: '余额燃尽', sortable: true, width: 118 },
  { key: 'used_total', title: '已消耗', sortable: true, width: 138 },
  { key: 'last_recharge_at', title: '最新充值', sortable: true, width: 102 },
]

// 列设置持久化 key
const STORAGE_KEY = 'balance_table_columns'

const tableColumns = computed<DataTableColumn[]>(() => [
  ...columnDefs.map((col) => ({
    key: col.key,
    title: col.title,
    width: col.width,
    sortable: col.sortable
      ? { sortDirections: ['ascend', 'descend'] as ('ascend' | 'descend')[] }
      : undefined,
  })),
  { key: 'action', title: '操作', slotName: 'action', fixed: 'right' as const, width: 170 },
])

// --- 分页配置：透传给 a-table 内置分页 ---
const paginationConfig = computed(() => ({
  current: props.pagination.current,
  pageSize: props.pagination.pageSize,
  total: props.pagination.total,
  showTotal: props.pagination.showTotal ?? true,
  showPageSize: props.pagination.showPageSize ?? true,
  showJumper: props.pagination.showJumper ?? true,
  pageSizeOptions: props.pagination.pageSizeOptions ?? [10, 20, 50, 100],
}))

// 前端列 key → 后端 sort_by 字段名映射
const sortFieldMap: Record<string, string> = {
  burn_down: 'days_remaining',
}

// --- 排序：a-table 三态 ascend/descend，清除时 emit 空字符串 ---
const onSorterChange = (dataIndex: string, direction: string) => {
  if (direction !== 'ascend' && direction !== 'descend') {
    emit('sortChange', '', '')
    return
  }
  const backendField = sortFieldMap[dataIndex] || dataIndex
  emit('sortChange', backendField, direction)
}

// --- 分页 ---
const onPageChange = (page: number) => {
  emit('pageChange', page)
}

const onPageSizeChange = (size: number) => {
  emit('pageSizeChange', size)
}

// --- 行高亮：即将耗尽红色 / 余额偏低黄色（样式由 DataTable 内置） ---
const rowClassFn = (record: unknown) => {
  const r = record as Balance
  if (isBurningSoon(r)) return 'row-warning'
  if (isBurningWarn(r)) return 'row-warn'
  return ''
}

// --- 辅助方法 ---
const BURN_MAX_DAYS = 60

const getInitials = (name?: string) => {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

const formatAmount = (num: number | null | undefined): string => {
  if (num == null) return '0.00'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 计数类数值（套餐剩余次数等）：千分位整数，无小数
const formatCount = (num: number | null | undefined): string => {
  if (num == null) return '0'
  return num.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

// 负余额 = 欠费（后付费客户未回款或预付费客户透支），红色高亮并加「欠费」标签；
// 零余额客户数量大（多为未消耗客户），标红只会淹没真正的风险行，故保持中性。
const isNegativeBalance = (record: Balance): boolean => {
  return record.total_amount < 0
}

// ===== 余额燃尽：油表进度条（满 = 安全，空 = 紧急）=====

// 行高亮：≤7 天红色背景（已过期包年有独立灰色标签，不叠加行高亮）
const isBurningSoon = (record: Balance): boolean => {
  if (record.package_expired) return false
  return record.days_remaining != null && record.days_remaining <= 7
}

// 行高亮：8-30 天浅黄色背景
const isBurningWarn = (record: Balance): boolean => {
  if (record.package_expired) return false
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
    return parts.join('\n')
  }

  const parts: string[] = []
  if (record.daily_avg_cost != null) {
    parts.push(`日均消耗 ¥${formatAmount(record.daily_avg_cost)}`)
  }
  parts.push(`30 天内有 ${record.consumption_days} 天消费记录`)

  const remaining = record.real_amount + record.bonus_amount
  parts.push(`当前余额 ¥${formatAmount(remaining)}`)

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
  return parts.join('\n')
}

// ===== 包年套餐燃尽：以「到期剩余天数」为口径 =====

// 包年进度条满格基准天数（一年）
const PACKAGE_BURN_MAX_DAYS = 365

// 进度条填充百分比：满格 = 距到期还很久（安全），空 = 即将/已到期
const getPackageBurnFillPct = (record: Balance): number => {
  if (record.days_remaining == null) return 100 // 无到期日 → 满格灰色
  if (record.days_remaining <= 0) return 0
  return Math.min((record.days_remaining / PACKAGE_BURN_MAX_DAYS) * 100, 100)
}

// 进度条颜色 class：≤30 天红、31-90 天黄、其余绿
const getPackageBurnBarClass = (record: Balance): string => {
  if (record.days_remaining == null) return 'no-data'
  if (record.days_remaining <= 30) return 'danger'
  if (record.days_remaining <= 90) return 'warn'
  return 'safe'
}

// 核心文字标签
const getPackageBurnLabel = (record: Balance): string => {
  if (record.days_remaining == null) return '无到期日'
  if (record.days_remaining <= 0) return '已到期'
  return `剩余 ${Math.floor(record.days_remaining)}天到期`
}

// tooltip 详情：套餐到期日期、剩余额度、剩余次数
const getPackageBurnTooltip = (record: Balance): string => {
  const parts: string[] = []
  if (record.package_expiry_date) {
    parts.push(`套餐到期：${record.package_expiry_date}`)
  } else {
    parts.push('套餐无固定到期日')
  }
  if (record.is_package && !record.package_expired) {
    parts.push(`套餐剩余额度 ¥${formatAmount(record.package_remaining_amount)}`)
    if (record.package_is_unlimited) {
      parts.push('套餐类型：不限量')
    } else if (record.package_remaining_count != null) {
      parts.push(`套餐剩余次数 ${formatCount(record.package_remaining_count)}`)
    }
    if (record.package_expiry_date && record.days_remaining != null) {
      parts.push(
        record.days_remaining > 0 ? `距到期 ${Math.floor(record.days_remaining)} 天` : '套餐已到期'
      )
    }
  }
  return parts.join('\n')
}

// 「已消耗」列包年 tooltip：说明该值为套餐内累计消耗（实时口径，与余额列同口径）
const getPackageConsumedTooltip = (record: Balance): string => {
  const parts: string[] = []
  parts.push(`套餐内累计消耗 ¥${formatAmount(record.package_consumed_amount)}`)
  if (record.package_base_fee != null) {
    parts.push(`套餐年费 ¥${formatAmount(record.package_base_fee)}`)
  }
  if (record.package_remaining_amount != null) {
    parts.push(`套餐剩余额度 ¥${formatAmount(record.package_remaining_amount)}`)
  }
  parts.push('包年为合同式预收，此消耗按每日用量实时累计（含未结算），不依赖结算单')
  return parts.join('\n')
}
</script>

<style scoped>
/* 表格骨架、表头、固定列阴影、行高亮由 DataTable 提供；
   此处仅保留余额管理页独有的单元格样式。 */

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
  margin-top: 1px;
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
  line-height: 1.25;
  white-space: nowrap;
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
  gap: 2px;
  min-width: 110px;
  cursor: help;
  justify-content: center;
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
  background: #94a3b8;
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
  margin-top: 1px;
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
  line-height: 1.25;
  white-space: nowrap;
}
.used-detail .used-real {
  color: #dc2626;
}
.used-detail .used-bonus {
  color: var(--muted);
}
/* 包年客户已消耗：实时口径提示文案 */
.used-detail .used-package {
  color: var(--muted);
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

/* 从未充值 */
.never-recharge {
  color: var(--muted);
}
</style>
