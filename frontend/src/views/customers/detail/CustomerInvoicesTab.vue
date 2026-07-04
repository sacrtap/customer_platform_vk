<template>
  <div class="data-table-card">
    <a-table :columns="invoiceColumns" :data="invoices" :pagination="false" row-key="id">
      <template #status="{ record }">
        <span :class="['status-badge', getStatusClass(record.status)]">
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

const getStatusClass = (status: string) => {
  const statusMap: Record<string, string> = {
    draft: 'warning',
    pending_customer: 'warning',
    customer_confirmed: 'success',
    paid: 'success',
    completed: 'success',
    cancelled: 'danger',
  }
  return statusMap[status] || 'warning'
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
  { title: '状态', slotName: 'status', width: 100, align: 'center' },
  { title: '创建时间', dataIndex: 'created_at', width: 170 },
  { title: '操作', slotName: 'action', width: 90, align: 'center' },
]
</script>

<style scoped>
.data-table-card {
  width: 100%;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.success {
  background: var(--success-1);
  color: var(--success-6);
}

.status-badge.warning {
  background: var(--warning-1);
  color: var(--warning-6);
}

.status-badge.danger {
  background: var(--danger-1);
  color: var(--danger-6);
}

.status-badge.info {
  background: var(--primary-1);
  color: var(--primary-6);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
</style>
