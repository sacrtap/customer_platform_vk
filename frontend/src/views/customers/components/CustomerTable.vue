<template>
  <div class="table-section">
    <a-table
      :columns="columns"
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
          <span v-if="record.is_key_customer" class="key-customer-badge" title="重点客户">★</span>
          <span class="name-text">{{ record.name }}</span>
        </div>
      </template>
      <template #createdAt="{ record }">
        {{ formatDateTime(record.created_at) }}
      </template>
      <template #settlementType="{ record }">
        {{ getSettlementTypeName(record.settlement_type) }}
      </template>
      <template #manager="{ record }">
        {{ getManagerName(record.manager_id) }}
      </template>
      <template #salesManager="{ record }">
        {{ getSalesManagerName(record.sales_manager_id) }}
      </template>
      <template #action="{ record }">
        <a-space>
          <a-button type="primary" size="small" @click="viewCustomer(record.id)">查看</a-button>
          <a-button
            v-if="can('customers:edit')"
            type="text"
            size="small"
            @click="openEditModal(record)"
            >编辑</a-button
          >
          <a-dropdown>
            <a-button type="text" size="small">更多</a-button>
            <template #content>
              <a-doption @click="viewProfile(record.id)">画像</a-doption>
              <a-doption
                v-if="can('customers:delete')"
                style="color: #ff4d4f"
                @click="() => handleDelete(record.id)"
                >删除</a-doption
              >
            </template>
          </a-dropdown>
        </a-space>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/formatters'
import type { Customer } from '@/types'

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
  selectedCustomerIds: number[]
  can: (permission: string) => boolean
}

defineProps<Props>()

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

// 表格列定义
const columns = [
  { title: '客户名称', dataIndex: 'name', slotName: 'name', width: 200 },
  { title: '账号类型', dataIndex: 'account_type', width: 120 },
  { title: '行业', dataIndex: 'industry', width: 120 },
  { title: '创建时间', dataIndex: 'created_at', slotName: 'createdAt', width: 180 },
  { title: '结算方式', dataIndex: 'settlement_type', slotName: 'settlementType', width: 100 },
  { title: '运营经理', dataIndex: 'manager_id', slotName: 'manager', width: 120 },
  { title: '销售经理', dataIndex: 'sales_manager_id', slotName: 'salesManager', width: 120 },
  { title: '操作', slotName: 'action', width: 200, fixed: 'right' },
]

// 辅助方法
const getSettlementTypeName = (type: string) => {
  const map: Record<string, string> = { prepaid: '预付费', postpaid: '后付费' }
  return map[type] || type || '-'
}

const getManagerName = (id: number) => {
  // TODO: 从 managers 字典中查找
  return id ? `#${id}` : '-'
}

const getSalesManagerName = (id: number) => {
  // TODO: 从 managers 字典中查找
  return id ? `#${id}` : '-'
}

// 事件转发
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
.table-section {
  background: var(--color-bg-1);
  border-radius: 4px;
  overflow: hidden;
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}

.key-customer-badge {
  color: #ff4d4f;
  font-size: 14px;
}

.name-text {
  font-weight: 500;
}
</style>
