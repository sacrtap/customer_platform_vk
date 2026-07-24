<template>
  <div class="invoices-tab">
    <div class="data-table-card">
      <a-table :columns="invoiceColumns" :data="invoices" :pagination="false" row-key="id">
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
import { formatCurrency } from '@/utils/formatters'
import EmptyState from '@/components/EmptyState.vue'

defineProps<{
  invoices: Invoice[]
}>()

const emit = defineEmits<{
  viewInvoice: [record: Invoice]
}>()

const getStatusTagClass = (status: string) => {
  const statusMap: Record<string, string> = {
    draft: 'gray',
    pending_customer: 'amber',
    customer_confirmed: 'blue',
    paid: 'green',
    completed: 'green',
    cancelled: 'red',
  }
  return statusMap[status] || 'gray'
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    draft: '草稿',
    pending_customer: '待客户确认',
    customer_confirmed: '客户已确认',
    paid: '已付款',
    completed: '已完成',
    cancelled: '已取消',
  }
  return statusMap[status] || status
}

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
