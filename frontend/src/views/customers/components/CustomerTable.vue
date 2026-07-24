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
              v-for="col in visibleColumns"
              :key="col.key"
              :class="getThClass(col)"
              @click="col.sortable && toggleSort(col.key)"
            >
              <span>{{ col.title }}</span>
              <span v-if="col.sortable" class="th-sort-indicator"></span>
            </th>
            <th>
              操作
              <button class="th-icon-btn" title="列设置" @click.stop="columnSettingVisible = true">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <circle cx="12" cy="12" r="3" />
                  <path
                    d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
                  />
                </svg>
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="record in customers"
            :key="record.id"
            :data-risk="getRiskLevel(record)"
            :class="{ 'row-warning': isRowWarning(record) }"
            @click="emit('view', record.id)"
          >
            <td @click.stop>
              <input
                type="checkbox"
                :checked="selectedCustomerIds.includes(record.id)"
                @change="emit('select', ($event.target as HTMLInputElement).checked, record)"
              />
            </td>
            <td v-for="col in visibleColumns" :key="col.key">
              <!-- 客户ID -->
              <template v-if="col.key === 'company_id'">
                <span class="cust-id">{{ record.company_id }}</span>
              </template>
              <!-- 客户名称 -->
              <template v-else-if="col.key === 'name'">
                <div class="customer">
                  <span class="logo">{{ getInitials(record.name) }}</span>
                  <b
                    v-if="truncateName(record.name, 6) !== record.name"
                    class="name-text has-tooltip"
                    :data-tooltip="record.name"
                    >{{ truncateName(record.name, 6) }}</b
                  >
                  <b v-else class="name-text">{{ record.name }}</b>
                </div>
              </template>
              <!-- 行业/标签 -->
              <template v-else-if="col.key === 'industry'">
                <span v-if="record.industry">{{ record.industry }}</span>
                <span v-if="record.is_key_customer" class="tag blue">重点</span>
                <span v-if="!record.industry && !record.is_key_customer" class="subtle">-</span>
              </template>
              <!-- 规模等级 -->
              <template v-else-if="col.key === 'scale_level'">
                <span v-if="record.scale_level">{{ record.scale_level }}</span>
                <span v-else class="subtle">-</span>
              </template>
              <!-- 消费等级 -->
              <template v-else-if="col.key === 'consume_level'">
                <span v-if="record.consume_level">{{ record.consume_level }}</span>
                <span v-else class="subtle">-</span>
              </template>
              <!-- 余额 -->
              <template v-else-if="col.key === 'balance'">
                <span v-if="record.balance != null">¥{{ formatNumber(record.balance) }}</span>
                <span v-else class="subtle">-</span>
              </template>
              <!-- 30天消耗 -->
              <template v-else-if="col.key === 'usage_30d'">
                <div
                  v-if="record.usage_30d != null && record.usage_30d > 0"
                  class="usage-cell has-tooltip"
                  :data-tooltip="`30天消耗 ¥${formatNumber(record.usage_30d_amount || 0)}`"
                >
                  <div class="bar">
                    <span :style="{ width: `${Math.min(100, record.usage_30d)}%` }"></span>
                  </div>
                </div>
                <span v-else class="subtle">-</span>
              </template>
              <!-- 健康度 -->
              <template v-else-if="col.key === 'health'">
                <span v-if="record.health" class="tag" :class="getHealthTagClass(record.health)">
                  {{ getHealthLabel(record.health) }}
                </span>
                <span v-else class="subtle">-</span>
              </template>
              <!-- 结算方式 -->
              <template v-else-if="col.key === 'settlement_type'">
                <span
                  v-if="record.settlement_type"
                  class="tag"
                  :class="record.settlement_type === 'prepaid' ? 'green' : 'blue'"
                >
                  {{ getSettlementTypeName(record.settlement_type) }}
                </span>
                <span v-else class="subtle">-</span>
              </template>
              <!-- 运营经理 -->
              <template v-else-if="col.key === 'manager_id'">
                {{ getManagerName(record.manager_id) }}
              </template>
              <!-- 销售经理 -->
              <template v-else-if="col.key === 'sales_manager_id'">
                {{ getSalesManagerName(record.sales_manager_id) }}
              </template>
              <!-- 账号类型 -->
              <template v-else-if="col.key === 'account_type'">
                {{ record.account_type || '-' }}
              </template>
              <!-- 创建时间 -->
              <template v-else-if="col.key === 'created_at'">
                {{ formatDateTime(record.created_at) }}
              </template>
            </td>
            <td style="white-space: nowrap" @click.stop>
              <button
                v-if="can('customers:edit')"
                class="btn"
                style="padding: 4px 10px; font-size: 12px"
                @click="emit('edit', record)"
              >
                编辑
              </button>
              <button
                class="btn"
                style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
                @click="emit('view', record.id)"
              >
                详情
              </button>
            </td>
          </tr>
          <tr v-if="customers.length === 0 && !loading">
            <td :colspan="visibleColumns.length + 2" class="empty-state">暂无客户数据</td>
          </tr>
          <tr v-if="loading">
            <td :colspan="visibleColumns.length + 2" class="loading-state">加载中...</td>
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

    <!-- 列设置弹窗 -->
    <ColumnSettingModal
      v-model:visible="columnSettingVisible"
      :columns="allColumnDefs"
      :model-value="visibleColumnKeys"
      @update:model-value="updateVisibleColumns"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { formatDateTime } from '@/utils/formatters'
import type { Customer } from '@/types'
import ColumnSettingModal from './ColumnSettingModal.vue'

interface Props {
  customers: Customer[]
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
  managers: Array<{ id: number; real_name: string | null }>
  managersLoading: boolean
  selectedCustomerIds: number[]
  can: (permission: string) => boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'select', checked: boolean, row: Customer): void
  (e: 'selectAll', checked: boolean): void
  (e: 'pageChange', page: number): void
  (e: 'pageSizeChange', pageSize: number): void
  (e: 'sortChange', dataIndex: string, direction: string): void
  (e: 'view', id: number): void
  (e: 'edit', record: Customer): void
  (e: 'delete', id: number): void
}>()

// --- 列定义 ---
interface ColumnDef {
  key: string
  title: string
  sortable?: boolean
  default: boolean
}

const allColumnDefs: ColumnDef[] = [
  { key: 'company_id', title: '客户ID', sortable: true, default: true },
  { key: 'name', title: '客户名称', sortable: true, default: true },
  { key: 'industry', title: '行业/标签', sortable: true, default: true },
  { key: 'scale_level', title: '规模等级', sortable: true, default: true },
  { key: 'consume_level', title: '消费等级', sortable: true, default: true },
  { key: 'balance', title: '余额', sortable: true, default: true },
  { key: 'usage_30d', title: '30天消耗', sortable: true, default: true },
  { key: 'health', title: '健康度', sortable: true, default: true },
  { key: 'settlement_type', title: '结算方式', sortable: true, default: false },
  { key: 'manager_id', title: '运营经理', sortable: true, default: true },
  { key: 'sales_manager_id', title: '销售经理', sortable: true, default: true },
  { key: 'account_type', title: '账号类型', sortable: true, default: false },
  { key: 'created_at', title: '创建时间', sortable: true, default: false },
]

// 列设置持久化
const STORAGE_KEY = 'customer_table_columns_config'
const visibleColumnKeys = ref<string[]>(loadColumnConfig())

function loadColumnConfig(): string[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return JSON.parse(saved)
  } catch {
    // ignore
  }
  return allColumnDefs.filter((c) => c.default).map((c) => c.key)
}

function updateVisibleColumns(keys: string[]) {
  visibleColumnKeys.value = keys
  localStorage.setItem(STORAGE_KEY, JSON.stringify(keys))
}

const columnSettingVisible = ref(false)

const visibleColumns = computed(() => {
  const keySet = new Set(visibleColumnKeys.value)
  return allColumnDefs.filter((col) => keySet.has(col.key))
})

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
  emit('sortChange', key, sortDir.value)
}

// --- 选择 ---
const allChecked = computed(() => {
  return (
    props.customers.length > 0 &&
    props.customers.every((c) => props.selectedCustomerIds.includes(c.id))
  )
})

const someChecked = computed(() => {
  return !allChecked.value && props.customers.some((c) => props.selectedCustomerIds.includes(c.id))
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
    if (current > 3) pages.push(-1) // ellipsis
    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)
    for (let i = start; i <= end; i++) pages.push(i)
    if (current < total - 2) pages.push(-1) // ellipsis
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
const getInitials = (name: string) => {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

const truncateName = (name: string, maxChars: number) => {
  if (!name) return ''
  if ([...name].length <= maxChars) return name
  return [...name].slice(0, maxChars).join('') + '…'
}

const formatNumber = (num: number | string) => {
  const n = typeof num === 'string' ? parseFloat(num) : num
  if (isNaN(n)) return '0'
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

const getSettlementTypeName = (type: string) => {
  const map: Record<string, string> = { prepaid: '预付费', postpaid: '后付费' }
  return map[type] || type || '-'
}

const getManagerName = (id: number | null) => {
  if (!id) return '-'
  const manager = props.managers.find((m) => m.id === id)
  return manager?.real_name || `#${id}`
}

const getSalesManagerName = (id: number | null) => {
  if (!id) return '-'
  const manager = props.managers.find((m) => m.id === id)
  return manager?.real_name || `#${id}`
}

const getHealthTagClass = (health: string) => {
  const map: Record<string, string> = {
    healthy: 'green',
    attention: 'amber',
    high_risk: 'red',
  }
  return map[health] || 'gray'
}

const getHealthLabel = (health: string) => {
  const map: Record<string, string> = {
    healthy: '健康',
    attention: '关注',
    high_risk: '高风险',
  }
  return map[health] || health
}

const getRiskLevel = (record: Customer) => {
  if (record.health === 'high_risk') return 'red'
  if (record.health === 'attention') return 'amber'
  if (record.health === 'healthy') return 'green'
  return ''
}

const isRowWarning = (record: Customer) => {
  return record.health === 'high_risk'
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
  position: sticky;
  top: 0;
  z-index: 1;
}
.table tbody tr {
  cursor: pointer;
  transition: background 0.15s;
}
.table tbody tr:hover td {
  background: #f8fbff;
}
.table tbody tr[data-risk='red'] td {
  background: rgba(220, 38, 38, 0.04);
}
.table tbody tr[data-risk='red']:hover td {
  background: rgba(220, 38, 38, 0.07);
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
  max-width: 180px;
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
/* 带 tooltip 时取消 overflow 裁剪（JS 已截断文本，无需 CSS 截断） */
.customer .name-text.has-tooltip {
  overflow: visible;
  text-overflow: clip;
}

/* 自定义 Tooltip */
.has-tooltip {
  position: relative;
  cursor: default;
}
.has-tooltip::before,
.has-tooltip::after {
  position: absolute;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
  z-index: 999;
}
.has-tooltip::before {
  content: attr(data-tooltip);
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  background: #1e293b;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
  padding: 6px 12px;
  border-radius: 8px;
  white-space: nowrap;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
.has-tooltip::after {
  content: '';
  bottom: calc(100% + 3px);
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  border: 5px solid transparent;
  border-top-color: #1e293b;
}
.has-tooltip:hover::before {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
.has-tooltip:hover::after {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
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
  margin-left: 6px;
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

.subtle {
  color: var(--muted);
  font-size: 12px;
}

/* 30天消耗单元格 */
.usage-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  cursor: default;
}

/* 进度条 */
.bar {
  height: 6px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
  min-width: 80px;
  max-width: 120px;
}
.bar span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2563eb, #06b6d4);
  transition: width 0.3s;
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

/* 表头图标按钮 */
.th-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  color: var(--muted);
  vertical-align: middle;
  margin-left: 4px;
  padding: 0;
  transition:
    background 0.15s,
    border-color 0.15s,
    color 0.15s;
}
.th-icon-btn:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: var(--primary);
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
