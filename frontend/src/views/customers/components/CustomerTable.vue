<template>
  <div class="table-card">
    <a-table
      :columns="visibleColumns"
      :data="customers"
      :loading="loading"
      row-key="id"
      :pagination="pagination"
      :scroll="{ x: 'max-content' }"
      :row-selection="{
        type: 'checkbox',
        showCheckedAll: true,
        onlyCurrent: false,
        selectedRowKeys: selectedCustomerIds,
      }"
      @select="handleBatchSelect"
      @select-all="handleBatchSelectAll"
      @page-change="handlePageChange"
      @page-size-change="handlePageSizeChange"
      @sorter-change="handleSort"
    >
      <template #name="{ record }">
        <div class="name-cell">
          <span class="customer-logo">{{ getInitials(record.name) }}</span>
          <div class="name-info">
            <span class="name-text">{{ record.name }}</span>
            <span v-if="record.is_key_customer" class="key-badge">重点</span>
          </div>
        </div>
      </template>

      <template #industry="{ record }">
        <span v-if="record.industry">{{ record.industry }}</span>
        <span v-else class="subtle">-</span>
      </template>

      <template #scale_level="{ record }">
        <span v-if="record.scale_level" class="level-tag">{{ record.scale_level }}</span>
        <span v-else class="subtle">-</span>
      </template>

      <template #consume_level="{ record }">
        <span v-if="record.consume_level" class="level-tag">{{ record.consume_level }}</span>
        <span v-else class="subtle">-</span>
      </template>

      <template #balance="{ record }">
        <span v-if="record.balance != null" class="balance-cell">
          ¥{{ formatNumber(record.balance) }}
        </span>
        <span v-else class="subtle">-</span>
      </template>

      <template #usage_30d="{ record }">
        <ProgressBar
          v-if="record.usage_30d != null"
          :value="Math.min(100, record.usage_30d)"
          :color="getUsageColor(record.usage_30d)"
        />
        <span v-else class="subtle">-</span>
      </template>

      <template #health="{ record }">
        <Tag v-if="record.health" :variant="getHealthVariant(record.health)">
          {{ getHealthLabel(record.health) }}
        </Tag>
        <span v-else class="subtle">-</span>
      </template>

      <template #settlementType="{ record }">
        <Tag :variant="record.settlement_type === 'prepaid' ? 'green' : 'blue'" size="sm">
          {{ getSettlementTypeName(record.settlement_type) }}
        </Tag>
      </template>

      <template #manager="{ record }">
        {{ getManagerName(record.manager_id) }}
      </template>

      <template #salesManager="{ record }">
        {{ getSalesManagerName(record.sales_manager_id) }}
      </template>

      <template #account_type="{ record }">
        {{ record.account_type || '-' }}
      </template>

      <template #createdAt="{ record }">
        {{ formatDateTime(record.created_at) }}
      </template>

      <template #action="{ record }">
        <a-space>
          <a-button type="primary" size="small" @click="viewCustomer(record.id)">
            查看
          </a-button>
          <a-button
            v-if="can('customers:edit')"
            type="text"
            size="small"
            @click="openEditModal(record)"
          >
            编辑
          </a-button>
          <a-dropdown>
            <a-button type="text" size="small">更多</a-button>
            <template #content>
              <a-doption @click="viewProfile(record.id)">画像</a-doption>
              <a-doption
                v-if="can('customers:delete')"
                style="color: var(--red)"
                @click="() => handleDelete(record.id)"
              >
                删除
              </a-doption>
            </template>
          </a-dropdown>
        </a-space>
      </template>
    </a-table>
  </div>

  <!-- 列设置弹窗 -->
  <ColumnSettingModal
    v-model:visible="columnSettingVisible"
    :columns="allColumnDefs"
    :model-value="visibleColumnKeys"
    @update:model-value="updateVisibleColumns"
  />
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { formatDateTime } from '@/utils/formatters'
import type { Customer } from '@/types'
import Tag from '@/components/ui/Tag.vue'
import ProgressBar from '@/components/ui/ProgressBar.vue'
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
  dataIndex?: string
  slotName?: string
  width?: number
  sortable?: boolean
  fixed?: string
  default: boolean // 默认可见
}

const allColumnDefs: ColumnDef[] = [
  { key: 'name', title: '客户', slotName: 'name', width: 200, default: true },
  { key: 'industry', title: '行业', slotName: 'industry', width: 120, default: true },
  { key: 'scale_level', title: '规模等级', slotName: 'scale_level', width: 100, default: true },
  { key: 'consume_level', title: '消费等级', slotName: 'consume_level', width: 100, default: true },
  { key: 'balance', title: '余额', slotName: 'balance', width: 120, sortable: true, default: true },
  { key: 'usage_30d', title: '30天消耗', slotName: 'usage_30d', width: 140, sortable: true, default: true },
  { key: 'health', title: '健康度', slotName: 'health', width: 100, default: true },
  { key: 'settlement_type', title: '结算方式', dataIndex: 'settlement_type', slotName: 'settlementType', width: 110, default: false },
  { key: 'manager_id', title: '运营经理', slotName: 'manager', width: 100, default: true },
  { key: 'sales_manager_id', title: '销售经理', slotName: 'salesManager', width: 100, default: true },
  { key: 'account_type', title: '账号类型', dataIndex: 'account_type', slotName: 'account_type', width: 110, default: false },
  { key: 'created_at', title: '创建时间', dataIndex: 'created_at', slotName: 'createdAt', width: 160, default: false },
  { key: 'action', title: '操作', slotName: 'action', width: 200, fixed: 'right', default: true },
]

// 列设置持久化
const STORAGE_KEY = 'customer_table_columns_config'
const visibleColumnKeys = ref< string[]>(loadColumnConfig())

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

// 计算的可见列
const visibleColumns = computed(() => {
  const keySet = new Set(visibleColumnKeys.value)
  return allColumnDefs
    .filter((col) => keySet.has(col.key))
    .map((col) => ({
      title: col.title,
      dataIndex: col.dataIndex || col.slotName || col.key,
      slotName: col.slotName,
      width: col.width,
      sortable: col.sortable,
      fixed: col.fixed,
    }))
})

// --- 辅助方法 ---
const getInitials = (name: string) => {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

const formatNumber = (num: number | string) => {
  const n = typeof num === 'string' ? parseFloat(num) : num
  if (isNaN(n)) return '0'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
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

const getUsageColor = (value: number) => {
  if (value >= 80) return '#059669'
  if (value >= 50) return '#3B82F6'
  return '#94A3B8'
}

const getHealthVariant = (health: string): 'green' | 'amber' | 'red' | 'gray' => {
  const map: Record<string, 'green' | 'amber' | 'red' | 'gray'> = {
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

// --- 事件转发 ---
const handleBatchSelect = (checked: boolean, row: Customer) => emit('select', checked, row)
const handleBatchSelectAll = (checked: boolean) => emit('selectAll', checked)
const handlePageChange = (page: number) => emit('pageChange', page)
const handlePageSizeChange = (pageSize: number) => emit('pageSizeChange', pageSize)
const handleSort = (dataIndex: string, direction: string) => emit('sortChange', dataIndex, direction)
const viewCustomer = (id: number) => emit('view', id)
const viewProfile = (id: number) => emit('view', id)
const openEditModal = (record: Customer) => emit('edit', record)
const handleDelete = (id: number) => emit('delete', id)
</script>

<style scoped>
.table-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

/* 客户名称单元格 */
.name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.customer-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.name-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.name-text {
  font-weight: 500;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.key-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: #dbeafe;
  color: #1d4ed8;
  flex-shrink: 0;
}

/* 等级标签 */
.level-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f1f5f9;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink);
}

.balance-cell {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--ink);
}

.subtle {
  color: var(--muted);
  font-size: 12px;
}

/* 表格表头样式 */
.table-card :deep(.arco-table-th) {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

/* 表格行 hover */
.table-card :deep(.arco-table-tr:hover .arco-table-td) {
  background: #f8fbff;
}

/* 分页器样式 */
.table-card :deep(.arco-pagination-item-active) {
  background: var(--primary);
  color: white;
}
</style>
