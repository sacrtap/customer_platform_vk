<template>
  <a-drawer
    v-model:visible="isVisible"
    title="结算单详情"
    width="720px"
    unmount-on-close
    :footer="false"
  >
    <template v-if="invoice">
      <div class="drawer-content">
        <div class="detail-header">
          <div class="detail-title">
            <h2>{{ invoice.invoice_no }}</h2>
            <InvoiceStatusBadge :status="invoice.status" />
            <span v-if="invoice.is_auto_generated" class="tag blue">自动</span>
          </div>
        </div>

        <a-descriptions :column="2" bordered size="small" class="detail-info">
          <a-descriptions-item label="客户名称">
            <a-link @click="emit('go-customer', invoice.customer_id)">{{
              invoice.customer_name
            }}</a-link>
          </a-descriptions-item>
          <a-descriptions-item label="结算周期">
            {{ formatDate(invoice.period_start) }} ~
            {{ formatDate(invoice.period_end) }}
          </a-descriptions-item>
          <a-descriptions-item label="总金额">{{
            formatCurrency(invoice.total_amount)
          }}</a-descriptions-item>
          <a-descriptions-item
            v-if="invoice.discount_amount && invoice.discount_amount > 0"
            label="折扣金额"
          >
            <span class="text-danger">-{{ formatCurrency(invoice.discount_amount) }}</span>
          </a-descriptions-item>
          <a-descriptions-item v-if="invoice.discount_reason" label="折扣原因" :span="2">{{
            invoice.discount_reason
          }}</a-descriptions-item>
          <a-descriptions-item label="折后金额">
            <span class="amount-final">{{ formatCurrency(invoice.final_amount) }}</span>
          </a-descriptions-item>
        </a-descriptions>

        <div class="detail-section">
          <div class="section-header"><h3>结算明细</h3></div>
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th style="width: 120px">设备类型</th>
                  <th style="width: 80px">图层</th>
                  <th style="width: 80px">数量</th>
                  <th style="width: 100px">单价</th>
                  <th style="width: 120px">小计</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in invoice.items || []" :key="item.id || idx">
                  <td>{{ item.device_type }}</td>
                  <td>
                    <span class="tag" :class="item.layer_type === 'multi' ? 'violet' : 'blue'">
                      {{ item.layer_type === 'multi' ? '多层' : '单层' }}
                    </span>
                  </td>
                  <td>{{ item.quantity }}</td>
                  <td>¥{{ item.unit_price.toFixed(2) }}</td>
                  <td>
                    <span class="amount">{{
                      formatCurrency(item.subtotal || item.quantity * item.unit_price)
                    }}</span>
                  </td>
                </tr>
                <tr v-if="!invoice.items || invoice.items.length === 0">
                  <td :colspan="5" class="empty-state">暂无结算明细</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="detail-section">
          <div class="section-header"><h3>操作记录</h3></div>
          <InvoiceTimeline :invoice="invoice" />
        </div>

        <div class="action-section">
          <button
            v-if="can('billing:edit') && invoice.status === 'draft'"
            class="btn primary"
            @click="emit('submit', invoice.id)"
          >
            提交
          </button>
          <!-- 运营经理确认：非指定经理时禁用并提示 -->
          <template v-if="can('billing:ops_approve') && invoice.status === 'pending_ops'">
            <button
              v-if="canConfirmOps"
              class="btn primary"
              @click="emit('confirm-ops', invoice.id)"
            >
              运营经理确认
            </button>
            <a-tooltip v-else :content="opsDisabledTip" position="top">
              <span class="btn primary disabled">运营经理确认</span>
            </a-tooltip>
          </template>
          <!-- 销售经理确认：非指定经理时禁用并提示 -->
          <template v-if="can('billing:sales_approve') && invoice.status === 'pending_sales'">
            <button
              v-if="canConfirmSales"
              class="btn primary"
              @click="emit('confirm-sales', invoice.id)"
            >
              销售经理确认
            </button>
            <a-tooltip v-else :content="salesDisabledTip" position="top">
              <span class="btn primary disabled">销售经理确认</span>
            </a-tooltip>
          </template>
          <button
            v-if="can('billing:confirm') && invoice.status === 'pending_customer'"
            class="btn primary"
            @click="emit('confirm', invoice.id)"
          >
            客户确认
          </button>
          <button
            v-if="can('billing:confirm') && invoice.status === 'customer_confirmed'"
            class="btn primary"
            :disabled="retrying"
            @click="emit('retry-deduction', invoice.id)"
          >
            {{ retrying ? '扣款中...' : '重试扣款' }}
          </button>
          <button
            v-if="
              can('billing:edit') &&
              ['draft', 'pending_ops', 'pending_sales', 'pending_customer'].includes(invoice.status)
            "
            class="btn btn-danger"
            @click="emit('cancel', invoice.id)"
          >
            取消结算单
          </button>
          <button class="btn" @click="isVisible = false">关闭</button>
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
  retrying?: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [id: number]
  'confirm-ops': [id: number]
  'confirm-sales': [id: number]
  confirm: [id: number]
  'retry-deduction': [id: number]
  cancel: [id: number]
  'go-customer': [id: number]
}>()

const userStore = useUserStore()
const can = (p: string) => userStore.hasPermission(p)

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

// ===== 经理身份校验：仅该客户指定的运营/销售经理可点击对应确认按钮 =====
// 超级管理员若非该客户指定经理，同样不可操作（与后端校验保持一致）
const currentUserId = computed(() => userStore.userInfo?.id)

// 是否可点击「运营经理确认」
const canConfirmOps = computed(() => {
  if (!props.invoice) return false
  return currentUserId.value === props.invoice.customer_manager_id
})

// 是否可点击「销售经理确认」
const canConfirmSales = computed(() => {
  if (!props.invoice) return false
  return currentUserId.value === props.invoice.customer_sales_manager_id
})

// 禁用时的 hover 提示文案
const opsDisabledTip = computed(() => {
  if (!props.invoice) return ''
  if (!props.invoice.customer_manager_id) {
    return '该客户尚未指定运营经理，无法确认'
  }
  return '您不是该客户指定的运营经理，无法确认'
})

const salesDisabledTip = computed(() => {
  if (!props.invoice) return ''
  if (!props.invoice.customer_sales_manager_id) {
    return '该客户尚未指定销售经理，无法确认'
  }
  return '您不是该客户指定的销售经理，无法确认'
})
</script>

<style scoped>
.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.detail-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.detail-title h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
  margin: 0;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  margin: 0;
}

/* 表格容器 */
.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 15px;
}
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
  font-weight: 600;
}
.table tbody tr {
  transition: background 0.15s;
}
.table tbody tr:hover td {
  background: #f8fbff;
}

/* 金额 */
.amount {
  font-weight: 500;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.amount-final {
  font-size: 16px;
  font-weight: 700;
  color: var(--primary);
}
.text-danger {
  color: var(--red);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 32px 20px;
  color: var(--muted);
  font-size: 14px;
}

/* 按钮 */
.btn {
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  border-radius: 12px;
  padding: 9px 16px;
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
.btn.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}
.btn.primary:hover {
  background: #1e40af;
}
/* 禁用状态：不可点击，灰色显示，配合 a-tooltip 提示原因 */
.btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: auto;
}
.btn.disabled:hover {
  background: var(--primary);
  border-color: var(--primary);
}
.btn.btn-danger {
  color: var(--red);
  border-color: #fecaca;
}
.btn.btn-danger:hover {
  background: #fef2f2;
  border-color: #fca5a5;
}

.action-section {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}
</style>
