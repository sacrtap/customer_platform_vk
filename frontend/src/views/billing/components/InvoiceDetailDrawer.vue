<template>
  <a-drawer v-model:visible="isVisible" title="结算单详情" width="720px" unmount-on-close>
    <template v-if="invoice">
      <div class="drawer-content">
        <div class="detail-header">
          <div class="detail-title">
            <h2>{{ invoice.invoice_no }}</h2>
            <InvoiceStatusBadge :status="invoice.status" />
            <a-tag v-if="invoice.is_auto_generated" color="blue" size="small">自动</a-tag>
          </div>
        </div>

        <a-descriptions :column="2" bordered size="small" class="detail-info">
          <a-descriptions-item label="客户名称"><a-link @click="emit('go-customer', invoice.customer_id)">{{ invoice.customer_name }}</a-link></a-descriptions-item>
          <a-descriptions-item label="结算周期">{{ formatDate(invoice.period_start) }} ~ {{ formatDate(invoice.period_end) }}</a-descriptions-item>
          <a-descriptions-item label="总金额">{{ formatCurrency(invoice.total_amount) }}</a-descriptions-item>
          <a-descriptions-item v-if="invoice.discount_amount && invoice.discount_amount > 0" label="折扣金额"><span class="text-danger">-{{ formatCurrency(invoice.discount_amount) }}</span></a-descriptions-item>
          <a-descriptions-item v-if="invoice.discount_reason" label="折扣原因" :span="2">{{ invoice.discount_reason }}</a-descriptions-item>
          <a-descriptions-item label="折后金额"><span class="amount-final">{{ formatCurrency(invoice.final_amount) }}</span></a-descriptions-item>
        </a-descriptions>

        <div class="detail-section">
          <div class="section-header"><h3>结算明细</h3></div>
          <a-table :columns="itemColumns" :data="invoice.items || []" :pagination="false" size="small" row-key="id">
            <template #layer_type="{ record }"><a-tag :color="record.layer_type === 'multi' ? 'purple' : 'blue'">{{ record.layer_type === 'multi' ? '多层' : '单层' }}</a-tag></template>
            <template #subtotal="{ record }"><span class="amount">{{ formatCurrency(record.subtotal || record.quantity * record.unit_price) }}</span></template>
            <template #empty><a-empty description="暂无结算明细" /></template>
          </a-table>
        </div>

        <div class="detail-section">
          <div class="section-header"><h3>操作记录</h3></div>
          <InvoiceTimeline :invoice="invoice" />
        </div>

        <div class="action-section">
          <a-space>
            <a-button v-if="can('billing:edit') && invoice.status === 'draft'" type="primary" @click="emit('submit', invoice.id)">提交</a-button>
            <a-button v-if="can('billing:confirm') && invoice.status === 'pending_customer'" @click="emit('confirm', invoice.id)">确认</a-button>
            <a-button v-if="can('billing:edit') && ['draft', 'pending_customer'].includes(invoice.status)" status="danger" @click="emit('cancel', invoice.id)">取消</a-button>
          </a-space>
        </div>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { formatCurrency, formatDate } from '@/utils/formatters'
import type { Invoice } from '@/api/billing'
import InvoiceStatusBadge from '@/components/invoice/InvoiceStatusBadge.vue'
import InvoiceTimeline from '@/components/invoice/InvoiceTimeline.vue'

const props = defineProps<{
  visible: boolean
  invoice: Invoice | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'submit': [id: number]
  'confirm': [id: number]
  'cancel': [id: number]
  'go-customer': [id: number]
}>()

const userStore = useUserStore()
const can = (p: string) => userStore.hasPermission(p)

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const itemColumns = [
  { title: '设备类型', dataIndex: 'device_type', width: 120 },
  { title: '图层', slotName: 'layer_type', width: 80 },
  { title: '数量', dataIndex: 'quantity', width: 80 },
  { title: '单价', dataIndex: 'unit_price', width: 100 },
  { title: '小计', slotName: 'subtotal', width: 120 },
]
</script>

<style scoped>
.drawer-content { display: flex; flex-direction: column; gap: 24px; }
.detail-title { display: flex; align-items: center; gap: 12px; }
.detail-title h2 { font-size: 20px; font-weight: 700; color: #2f3645; margin: 0; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-header h3 { font-size: 16px; font-weight: 600; color: #2f3645; margin: 0; }
.amount { font-weight: 500; color: #2f3645; }
.amount-final { font-size: 16px; font-weight: 700; color: #0369a1; }
.text-danger { color: #ef4444; }
.action-section { display: flex; justify-content: flex-end; padding-top: 16px; border-top: 1px solid #eef0f3; }
</style>
