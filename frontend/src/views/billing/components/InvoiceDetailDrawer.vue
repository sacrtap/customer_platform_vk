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
          <a-descriptions-item label="减免金额">
            <span
              v-if="invoice.discount_amount && invoice.discount_amount !== 0"
              :class="invoice.discount_amount > 0 ? 'text-danger' : 'text-success'"
            >
              {{ invoice.discount_amount > 0 ? '-' : '+'
              }}{{ formatCurrency(Math.abs(invoice.discount_amount)) }}
            </span>
            <span v-else class="subtle">无减免</span>
          </a-descriptions-item>
          <a-descriptions-item
            v-if="
              invoice.discount_reason || (invoice.discount_amount && invoice.discount_amount !== 0)
            "
            label="减免说明"
            :span="2"
            >{{ invoice.discount_reason || '—' }}</a-descriptions-item
          >
          <a-descriptions-item v-if="invoice.discount_attachment" label="减免附件" :span="2">
            <a :href="invoice.discount_attachment" target="_blank" download class="attachment-link"
              >查看附件</a
            >
          </a-descriptions-item>
          <a-descriptions-item label="最终结算金额">
            <span class="amount-final">{{ formatCurrency(invoice.final_amount) }}</span>
          </a-descriptions-item>
          <a-descriptions-item v-if="invoice.detail_file_status" label="明细文件">
            <div class="detail-file-section">
              <span v-if="invoice.detail_file_status === 'completed'" class="file-status completed"
                >✅ 已生成</span
              >
              <span
                v-else-if="invoice.detail_file_status === 'generating'"
                class="file-status generating"
                >⏳ 生成中...</span
              >
              <span v-else-if="invoice.detail_file_status === 'failed'" class="file-status failed"
                >❌ 生成失败</span
              >
              <span v-else class="file-status pending">— 待生成</span>
              <button
                v-if="can('billing:view') && invoice.detail_file_status === 'completed'"
                class="btn btn-sm"
                @click="handleDownload"
              >
                下载明细
              </button>
              <button
                v-if="can('billing:edit') && invoice.detail_file_status === 'failed'"
                class="btn btn-sm"
                @click="handleRegenerate"
              >
                重新生成
              </button>
            </div>
          </a-descriptions-item>
        </a-descriptions>

        <div class="detail-section">
          <div class="section-header"><h3>计费明细</h3></div>
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th style="width: 80px">计费类型</th>
                  <th style="width: 80px">设备类型</th>
                  <th style="width: 70px">楼层</th>
                  <th style="width: 90px">用量</th>
                  <th>计费规则</th>
                  <th style="width: 120px">小计</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in invoice.items || []" :key="item.id || idx">
                  <td>
                    <span :class="['pricing-tag', `pricing-${item.pricing_type}`]">
                      {{ pricingTypeText(item.pricing_type) }}
                    </span>
                  </td>
                  <td>{{ item.device_type || '—' }}</td>
                  <td>
                    <span
                      v-if="item.layer_type"
                      class="tag"
                      :class="item.layer_type === 'multi' ? 'violet' : 'blue'"
                    >
                      {{ item.layer_type === 'multi' ? '多层' : '单层' }}
                    </span>
                    <span v-else class="subtle">—</span>
                  </td>
                  <td>
                    <div class="rule-detail">
                      <div v-for="(line, lIdx) in formatQuantity(item)" :key="lIdx">{{ line }}</div>
                    </div>
                  </td>
                  <td>
                    <div class="rule-detail">
                      <div v-for="(line, rIdx) in formatRuleDetail(item)" :key="rIdx">
                        {{ line }}
                      </div>
                    </div>
                  </td>
                  <td>
                    <span class="amount">{{
                      formatCurrency(item.subtotal || item.quantity * item.unit_price)
                    }}</span>
                  </td>
                </tr>
                <tr v-if="!invoice.items || invoice.items.length === 0">
                  <td :colspan="6" class="empty-state">暂无计费明细</td>
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
          <!-- 修改减免：在 draft / pending_ops / pending_sales / pending_customer 状态下可修改 -->
          <button
            v-if="
              can('billing:edit') &&
              ['draft', 'pending_ops', 'pending_sales', 'pending_customer'].includes(invoice.status)
            "
            class="btn"
            @click="emit('edit-discount', invoice.id)"
          >
            {{ invoice.discount_amount ? '修改减免' : '设置减免' }}
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
import { Message } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import { formatCurrency, formatDate } from '@/utils/formatters'
import { pricingTypeText, formatQuantity, formatRuleDetail } from '@/utils/invoiceFormatters'
import { downloadInvoiceDetail, regenerateInvoiceDetail } from '@/api/billing'
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
  'edit-discount': [id: number]
  'confirm-ops': [id: number]
  'confirm-sales': [id: number]
  confirm: [id: number]
  'retry-deduction': [id: number]
  cancel: [id: number]
  'go-customer': [id: number]
  'regenerate-detail': [id: number]
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

// ===== 明细文件下载/重试 =====
const handleDownload = async () => {
  if (!props.invoice) return
  try {
    const res = await downloadInvoiceDetail(props.invoice.id)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `${props.invoice.customer_name}-${props.invoice.invoice_no}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
  } catch {
    Message.error('下载失败')
  }
}

const handleRegenerate = async () => {
  if (!props.invoice) return
  try {
    await regenerateInvoiceDetail(props.invoice.id)
    Message.success('明细文件重新生成中')
    // 通知父组件启动轮询
    emit('regenerate-detail', props.invoice.id)
  } catch {
    Message.error('操作失败')
  }
}
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
.incremental-cell {
  display: block;
  font-size: 11px;
  color: #64748b;
}
.amount-final {
  font-size: 16px;
  font-weight: 700;
  color: var(--primary);
}
.text-danger {
  color: var(--red);
}
.text-success {
  color: var(--green, #10b981);
}

/* 明细文件区域 */
.detail-file-section {
  display: flex;
  align-items: center;
  gap: 8px;
}
.file-status.completed {
  color: var(--green, #10b981);
}
.file-status.generating {
  color: var(--muted);
}
.file-status.failed {
  color: var(--red);
}
.file-status.pending {
  color: var(--muted);
}

.subtle {
  color: var(--muted);
}

/* 计费类型标签 */
.pricing-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}
.pricing-fixed {
  background: #e0f2fe;
  color: #0284c7;
}
.pricing-tiered {
  background: #dcfce7;
  color: #16a34a;
}
.pricing-package {
  background: #fef3c7;
  color: #d97706;
}

/* 计费规则详情（多行文本） */
.rule-detail {
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
}
.attachment-link {
  color: var(--primary);
  text-decoration: underline;
}

/* 小按钮 */
.btn.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 8px;
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
