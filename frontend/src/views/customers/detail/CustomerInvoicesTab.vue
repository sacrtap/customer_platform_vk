<template>
  <div class="invoices-tab">
    <div class="data-table-card">
      <a-table
        :columns="invoiceColumns"
        :data="invoices"
        :pagination="pagination"
        row-key="id"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
      >
        <template #status="{ record }">
          <span :class="['tag', getStatusTagClass(record.status)]">
            <span class="status-dot"></span>
            {{ getStatusText(record.status) }}
          </span>
        </template>
        <template #amount="{ record }">
          {{ formatCurrency(record.final_amount || record.total_amount) }}
        </template>
        <template #action="{ record }">
          <a-button type="primary" size="small" @click="emit('viewInvoice', record)">查看</a-button>
        </template>
        <template #empty>
          <EmptyState title="暂无结算单数据" description="当前客户暂无结算单" />
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Invoice } from '@/api/billing'
import { reactive, watch } from 'vue'
import { formatCurrency } from '@/utils/formatters'
import EmptyState from '@/components/EmptyState.vue'
import { getInvoiceStatusLabel, getInvoiceStatusColor } from '@/constants/invoiceStatus'

const props = defineProps<{
  invoices: Invoice[]
}>()

const emit = defineEmits<{
  viewInvoice: [record: Invoice]
}>()

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50],
})

// 当 invoices 变化时更新分页
watch(
  () => props.invoices,
  (newInvoices) => {
    pagination.total = newInvoices.length
  },
  { immediate: true }
)

const onPageChange = (page: number) => {
  pagination.current = page
}

const onPageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
}

const getStatusTagClass = getInvoiceStatusColor
const getStatusText = getInvoiceStatusLabel

const invoiceColumns = [
  { title: '结算单号', dataIndex: 'invoice_no' },
  { title: '周期开始', dataIndex: 'period_start', width: 120 },
  { title: '周期结束', dataIndex: 'period_end', width: 120 },
  { title: '金额', slotName: 'amount', width: 130, align: 'right' },
  { title: '状态', slotName: 'status', width: 120, align: 'center' },
  { title: '创建时间', dataIndex: 'created_at', width: 170 },
  { title: '操作', slotName: 'action', width: 90, align: 'center' },
]
</script>

<style scoped>
.invoices-tab {
  width: 100%;
}

.data-table-card {
  width: 100%;
}

/* 表头样式 */
.data-table-card :deep(.arco-table-th) {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

/* 行 hover */
.data-table-card :deep(.arco-table-tr:hover .arco-table-td) {
  background: #f8fbff;
}

/* 状态标签 */
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  margin-right: 4px;
}
</style>
