<template>
  <DataTable
    :columns="tableColumns"
    :data="customers as unknown as Record<string, unknown>[]"
    :loading="loading"
    :pagination="paginationConfig"
    :row-key="'id'"
    :row-selection="rowSelectionConfig"
    :row-class="rowClassFn"
    :scroll="{ x: 1318 }"
    :storage-key="STORAGE_KEY"
    @page-change="onPageChange"
    @page-size-change="onPageSizeChange"
    @sorter-change="onSorterChange"
    @row-click="onRowClick"
    @select="onRowSelect"
    @select-all="onSelectAll"
  >
    <template #company_id="{ record }">
      <span class="cust-id">{{ (record as Customer).company_id }}</span>
    </template>

    <template #name="{ record }">
      <div class="customer">
        <span class="logo">{{ getInitials((record as Customer).name) }}</span>
        <b
          v-if="truncateName((record as Customer).name, 8) !== (record as Customer).name"
          class="name-text has-tooltip"
          :data-tooltip="(record as Customer).name"
          >{{ truncateName((record as Customer).name, 8) }}</b
        >
        <b v-else class="name-text">{{ (record as Customer).name }}</b>
      </div>
    </template>

    <template #industry="{ record }">
      <span class="industry-cell">
        <span v-if="(record as Customer).industry" class="industry-name">{{
          (record as Customer).industry
        }}</span>
        <span v-if="(record as Customer).is_key_customer" class="tag blue">重点</span>
        <span
          v-if="!(record as Customer).industry && !(record as Customer).is_key_customer"
          class="subtle"
          >-</span
        >
      </span>
    </template>

    <template #scale_level="{ record }">
      <span v-if="(record as Customer).scale_level">{{ (record as Customer).scale_level }}</span>
      <span v-else class="subtle">-</span>
    </template>

    <template #consume_level="{ record }">
      <span v-if="(record as Customer).consume_level">{{
        (record as Customer).consume_level
      }}</span>
      <span v-else class="subtle">-</span>
    </template>

    <template #balance="{ record }">
      <span v-if="(record as Customer).balance != null">
        <a-tooltip
          v-if="(record as Customer).is_package"
          content="包年套餐剩余额度（年费为合同式预收，不进余额池）"
        >
          {{ formatCurrency((record as Customer).balance) }}
          <span v-if="(record as Customer).package_expired" class="subtle">（已过期）</span>
        </a-tooltip>
        <template v-else>{{ formatCurrency((record as Customer).balance) }}</template>
      </span>
      <span v-else class="subtle">-</span>
    </template>

    <template #usage_30d="{ record }">
      <div
        v-if="(record as Customer).usage_30d != null && (record as Customer).usage_30d > 0"
        class="usage-cell has-tooltip"
        :data-tooltip="`30天消耗 ${formatCurrency((record as Customer).usage_30d_amount || 0)}`"
      >
        <div class="bar">
          <span :style="{ width: `${Math.min(100, (record as Customer).usage_30d!)}%` }"></span>
        </div>
      </div>
      <span v-else class="subtle">-</span>
    </template>

    <template #health="{ record }">
      <span
        v-if="(record as Customer).health"
        class="tag has-tooltip"
        :class="getHealthTagClass((record as Customer).health)"
        :data-tooltip="healthTooltip(record as Customer)"
      >
        {{ getHealthLabel((record as Customer).health) }}
      </span>
      <span v-else class="subtle">-</span>
    </template>

    <template #settlement_type="{ record }">
      <span
        v-if="(record as Customer).settlement_type"
        class="tag"
        :class="(record as Customer).settlement_type === 'prepaid' ? 'green' : 'blue'"
      >
        {{ getSettlementTypeName((record as Customer).settlement_type) }}
      </span>
      <span v-else class="subtle">-</span>
    </template>

    <template #manager_id="{ record }">
      {{ getManagerName((record as Customer).manager_id) }}
    </template>

    <template #sales_manager_id="{ record }">
      {{ getSalesManagerName((record as Customer).sales_manager_id) }}
    </template>

    <template #account_type="{ record }">
      {{ (record as Customer).account_type || '-' }}
    </template>

    <template #created_at="{ record }">
      {{ formatDateTime((record as Customer).created_at) }}
    </template>

    <template #action="{ record }">
      <span class="action-cell">
        <button
          v-if="can('customers:edit')"
          class="btn"
          @click.stop="emit('edit', record as Customer)"
        >
          编辑
        </button>
        <button class="btn" @click.stop="emit('view', (record as Customer).id)">详情</button>
        <button
          v-if="can('customers:delete')"
          class="btn btn-danger"
          @click.stop="emit('delete', (record as Customer).id)"
        >
          删除
        </button>
      </span>
    </template>
  </DataTable>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatCurrency, formatDateTime } from '@/utils/formatters'
import type { Customer } from '@/types'
import DataTable, { type DataTableColumn } from '@/components/DataTable.vue'

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

// --- 列定义（key/title 沿用原 allColumnDefs，default → defaultVisible） ---
interface ColumnDef {
  key: string
  title: string
  sortable?: boolean
  default: boolean
  width?: number
}

const allColumnDefs: ColumnDef[] = [
  { key: 'company_id', title: '客户ID', sortable: true, default: true, width: 72 },
  { key: 'name', title: '客户名称', sortable: true, default: true, width: 172 },
  { key: 'industry', title: '行业/标签', sortable: true, default: true, width: 122 },
  { key: 'scale_level', title: '规模等级', sortable: true, default: true, width: 76 },
  { key: 'consume_level', title: '消费等级', sortable: true, default: true, width: 76 },
  { key: 'balance', title: '余额', sortable: true, default: true, width: 104 },
  { key: 'usage_30d', title: '30天消耗', sortable: true, default: true, width: 98 },
  { key: 'health', title: '健康度', sortable: false, default: true, width: 72 },
  { key: 'settlement_type', title: '结算方式', sortable: true, default: false, width: 84 },
  { key: 'manager_id', title: '运营经理', sortable: true, default: true, width: 80 },
  { key: 'sales_manager_id', title: '销售经理', sortable: true, default: true, width: 80 },
  { key: 'account_type', title: '账号类型', sortable: true, default: false, width: 84 },
  { key: 'created_at', title: '创建时间', sortable: true, default: false, width: 162 },
]

// 存量用户 localStorage 配置 key：必须与原实现一致，迁移后用户列设置不丢失
const STORAGE_KEY = 'customer_table_columns_config'

// 列定义转成 DataTable 列结构（操作列固定右侧）
const tableColumns = computed<DataTableColumn[]>(() => [
  ...allColumnDefs.map((col) => ({
    key: col.key,
    title: col.title,
    width: col.width,
    defaultVisible: col.default,
    sortable: col.sortable
      ? { sortDirections: ['ascend', 'descend'] as ('ascend' | 'descend')[] }
      : undefined,
  })),
  { key: 'action', title: '操作', slotName: 'action', fixed: 'right' as const, width: 140 },
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

// --- 多选 ---
const rowSelectionConfig = computed(() => ({
  type: 'checkbox' as const,
  showCheckedAll: true,
  onlyCurrent: false,
  selectedRowKeys: props.selectedCustomerIds,
}))

const onRowSelect = (rowKeys: unknown[], _rowKey: unknown, record: unknown) => {
  // arco select 回调签名：(rowKeys, rowKey, record)；转为原 (checked, row)
  const checked = (rowKeys as number[]).includes((record as Customer).id)
  emit('select', checked, record as Customer)
}

const onSelectAll = (checked: boolean) => {
  emit('selectAll', checked)
}

// --- 排序：a-table 三态，映射为原 toggleSort 的 (dataIndex, direction) ---
const onSorterChange = (dataIndex: string, direction: string) => {
  emit('sortChange', dataIndex, direction === 'ascend' || direction === 'descend' ? direction : '')
}

// --- 行点击进详情（原 <tr @click>） ---
const onRowClick = (record: unknown) => {
  emit('view', (record as Customer).id)
}

// --- 行高亮：高风险客户红色背景（样式由 DataTable 内置） ---
const rowClassFn = (record: unknown) => {
  return (record as Customer).health === 'high_risk' ? 'row-warning' : ''
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
    inactive: 'gray',
  }
  return map[health] || 'gray'
}

const getHealthLabel = (health: string) => {
  const map: Record<string, string> = {
    healthy: '健康',
    attention: '关注',
    high_risk: '高风险',
    inactive: '不活跃',
  }
  return map[health] || health
}

// 列表「简易健康度」判定口径说明（与详情页「健康度评分」是两套口径，tooltip 标注差异）：
// - inactive：近 30 天无消耗（先判用量，后判余额）
// - 后付费客户不参与余额判定（有消耗即健康，欠款属应收款范畴）
// - 预付费/未设置：有效余额 < 500 → 高风险，< 1000 → 关注，否则健康
const healthTooltip = (record: Customer): string => {
  const h = record.health
  const base = '列表简易估算：'
  if (h === 'inactive') return `${base}近 30 天无消耗`
  if (h === 'high_risk') return `${base}有效余额低于 500 元（预付口径）`
  if (h === 'attention') return `${base}有效余额低于 1000 元（预付口径）`
  if (h === 'healthy') {
    return record.settlement_type === 'postpaid'
      ? `${base}后付费客户有消耗（不按余额判定，欠款属应收款）`
      : `${base}有效余额充足且有消耗`
  }
  return base
}

// --- 分页事件 ---
const onPageChange = (page: number) => {
  emit('pageChange', page)
}

const onPageSizeChange = (pageSize: number) => {
  emit('pageSizeChange', pageSize)
}
</script>

<style scoped>
/* 表格骨架（.table-section/.table/.table-wrap）与分页样式由 DataTable 提供，
   此处仅保留客户管理页独有的单元格样式。 */

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
  width: 100%;
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
  flex: 1;
  min-width: 0;
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

/* 行业/标签单元格：flex 布局防止行业名与"重点"标签换行 */
.industry-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.industry-cell .industry-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.industry-cell .tag {
  flex-shrink: 0;
  margin-left: 0;
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

/* 健康度标签 tooltip：文案较长，允许换行并放宽宽度（覆盖通用 has-tooltip 的 nowrap/320px） */
.tag.has-tooltip::before {
  white-space: normal;
  max-width: 260px;
  overflow: visible;
  text-overflow: clip;
  text-align: left;
  width: max-content;
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
  padding: 0;
  cursor: default;
}

/* 进度条 */
.bar {
  height: 6px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
  width: 100%;
  min-width: 0;
  flex: 1;
}
.bar span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2563eb, #06b6d4);
  transition: width 0.3s;
}

/* 操作列按钮组：flex 布局消除 inline 元素间空白文本节点，紧凑排布 */
.action-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.action-cell .btn {
  padding: 4px 6px;
  font-size: 12px;
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
.btn-danger {
  color: #dc2626;
}
.btn-danger:hover {
  border-color: #fca5a5;
  background: #fef2f2;
}
</style>
