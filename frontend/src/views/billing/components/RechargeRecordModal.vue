<template>
  <a-modal
    v-model:visible="isVisible"
    title="余额记录"
    :footer="false"
    width="1160px"
    @cancel="emit('update:visible', false)"
  >
    <a-tabs v-model:active-key="activeTab" @change="handleTabChange">
      <!-- 充值记录 -->
      <a-tab-pane key="recharge" title="充值记录">
        <a-table
          :columns="rechargeColumns"
          :data="rechargeRecords"
          :loading="rechargeLoading"
          row-key="id"
          :pagination="rechargePagination"
          :scroll="{ x: 1045 }"
          @page-change="handleRechargePageChange"
        >
          <template #amount="{ record }">
            <div>{{ formatCurrency(record.total_amount) }}</div>
            <div class="amount-detail">
              <span class="real">实：{{ formatCurrency(record.real_amount) }}</span>
              <span class="bonus">赠：{{ formatCurrency(record.bonus_amount) }}</span>
            </div>
          </template>
          <template #source="{ record }">
            <span v-if="record.crm_payment_id" class="source-crm">
              CRM回款 #{{ record.crm_payment_external_id ?? record.crm_payment_id }}
            </span>
            <span v-else>手动/导入</span>
          </template>
          <template #recharge_date="{ record }">{{ formatDate(record.recharge_date) }}</template>
          <template #created_at="{ record }">{{ formatDateTime(record.created_at) }}</template>
          <template #recharge_action="{ record }">
            <button
              v-if="canRevoke(record)"
              class="btn-revoke"
              style="padding: 4px 10px; font-size: 12px"
              @click.stop="openRevokeModal(record as RechargeRecord)"
            >
              撤销
            </button>
            <span v-else class="subtle">-</span>
          </template>
        </a-table>
      </a-tab-pane>

      <!-- 消耗记录 -->
      <a-tab-pane key="consumption" title="消耗记录">
        <a-table
          :columns="consumptionColumns"
          :data="consumptionRecords"
          :loading="consumptionLoading"
          row-key="id"
          :pagination="consumptionPagination"
          @page-change="handleConsumptionPageChange"
        >
          <template #amount="{ record }">
            <div class="consumption-amount">{{ formatCurrency(record.amount) }}</div>
            <div class="amount-detail">
              <span class="real">实：{{ formatCurrency(record.real_used) }}</span>
              <span class="bonus">赠：{{ formatCurrency(record.bonus_used) }}</span>
            </div>
          </template>
          <template #balance_after="{ record }">
            <span class="balance-after">{{ formatCurrency(record.balance_after) }}</span>
          </template>
          <template #actual_customer="{ record }">
            <span v-if="record.actual_customer_name">
              {{ record.actual_customer_name }}
              <span class="customer-id">（ID: {{ record.actual_company_id }}）</span>
            </span>
            <span v-else>-</span>
          </template>
          <template #invoice_no="{ record }">
            <a
              v-if="record.invoice_no"
              :href="`/billing/invoices?highlight=${record.invoice_id}`"
              target="_blank"
              class="invoice-link"
              >{{ record.invoice_no }}</a
            >
            <a
              v-else-if="record.vr_settlement_no"
              :href="`/billing/vr-settlements?highlight=${record.vr_settlement_id}`"
              target="_blank"
              class="invoice-link"
              >{{ record.vr_settlement_no }}</a
            >
            <span v-else>-</span>
          </template>
          <template #consumed_at="{ record }">{{ formatDateTime(record.consumed_at) }}</template>
        </a-table>
      </a-tab-pane>
    </a-tabs>
  </a-modal>

  <!-- 撤销充值记录 -->
  <a-modal
    v-model:visible="revokeVisible"
    title="撤销充值记录"
    width="560px"
    :ok-loading="revoking"
    ok-text="确认撤销"
    @before-ok="submitRevoke"
  >
    <div v-if="revokeTarget" class="revoke-body">
      <div class="revoke-row">
        <span class="label">客户</span>
        <span>{{ revokeTarget.customer_name || `#${revokeTarget.customer_id}` }}</span>
      </div>
      <div class="revoke-row">
        <span class="label">入账金额</span>
        <span class="amount">
          实充 {{ formatCurrency(revokeTarget.real_amount) }} / 赠送
          {{ formatCurrency(revokeTarget.bonus_amount) }}
        </span>
      </div>
      <div class="revoke-row">
        <span class="label">来源</span>
        <span>手动/导入</span>
      </div>
      <div class="revoke-row">
        <span class="label">归期</span>
        <span>{{ formatDate(revokeTarget.recharge_date) }}</span>
      </div>
      <div class="revoke-row">
        <span class="label">入账时间</span>
        <span>{{ formatDateTime(revokeTarget.created_at) }}</span>
      </div>
      <div class="revoke-row">
        <span class="label">撤销后余额</span>
        <span class="amount-strong">
          {{ formatCurrency(revokePreviewBalance) }}
        </span>
      </div>
      <a-form layout="vertical" style="margin-top: 12px">
        <a-form-item label="撤销原因（必填，写入审计）">
          <a-textarea
            v-model="revokeReason"
            :auto-size="{ minRows: 2, maxRows: 4 }"
            placeholder="例如：充错客户，需撤销后重新充值"
          />
        </a-form-item>
        <a-form-item v-if="isSuperAdmin">
          <a-checkbox v-model="revokeForce">余额不足时强制撤销（线下核对欠款）</a-checkbox>
        </a-form-item>
      </a-form>
      <p class="revoke-tip">
        撤销会立即扣回该笔「实充 + 赠送」，记录从列表移除但原始凭据保留（可在审计中追溯）。
        余额已被消耗时，只有超级管理员可强制撤销，撤销后余额可为负（表示欠款）。
      </p>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  getRechargeRecords,
  getConsumptionRecords,
  getCustomerBalance,
  revokeRechargeRecord,
} from '@/api/billing'
import type { RechargeRecord, ConsumptionRecord } from '@/api/billing'
import { formatCurrency, formatDate, formatDateTime } from '@/utils/formatters'
import { handleError } from '@/utils/errorHandler'

const props = defineProps<{
  visible: boolean
  customerId?: number
  /** 权限判定（由父页面注入，组件不直接依赖 user store） */
  can?: (permission: string) => boolean
  isSuperAdmin?: boolean
}>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  /** 撤销成功：余额已变化，父页面需刷新余额列表 */
  revoked: [customerId: number]
}>()

const can = (permission: string) => props.can?.(permission) ?? false
const isVisible = computed({ get: () => props.visible, set: (val) => emit('update:visible', val) })

const activeTab = ref<'recharge' | 'consumption'>('recharge')

// ===== 充值记录 =====
const rechargeLoading = ref(false)
const rechargeRecords = ref<RechargeRecord[]>([])
const rechargePagination = reactive({ current: 1, pageSize: 10, showTotal: true })

const rechargeColumns = [
  { title: '客户', dataIndex: 'customer_name', width: 160 },
  { title: '充值金额', slotName: 'amount', width: 210 },
  { title: '来源', slotName: 'source', width: 130 },
  { title: '归期（回款日）', slotName: 'recharge_date', width: 120 },
  { title: '入账时间', slotName: 'created_at', width: 165 },
  { title: '备注', dataIndex: 'remark', width: 180 },
  { title: '操作', slotName: 'recharge_action', width: 80 },
]

// 撤销入口：CRM 来源须走 CRM 回款页（那里还要释放回款绑定）
const canRevoke = (record: RechargeRecord) =>
  !record.crm_payment_id && can('billing:recharge_revoke')

const revokeVisible = ref(false)
const revoking = ref(false)
const revokeTarget = ref<RechargeRecord | null>(null)
const revokeReason = ref('')
const revokeForce = ref(false)

// 撤销后余额 = 当前余额 - 该笔（仅预览，实际以服务端扣减结果为准）
const revokeCurrentBalance = ref(0)
const revokePreviewBalance = computed(
  () => revokeCurrentBalance.value - (revokeTarget.value?.total_amount ?? 0)
)

const openRevokeModal = async (record: RechargeRecord) => {
  revokeTarget.value = record
  revokeReason.value = ''
  revokeForce.value = false
  revokeVisible.value = true
  revokeCurrentBalance.value = 0
  try {
    const res = await getCustomerBalance(record.customer_id)
    revokeCurrentBalance.value = Number(res.data?.total_amount ?? 0)
  } catch {
    // 余额取不到时预览按 0 处理，实际扣减仍由服务端判定
  }
}

const submitRevoke = async (): Promise<boolean> => {
  const target = revokeTarget.value
  if (!target) return false
  if (!revokeReason.value.trim()) {
    Message.warning('请填写撤销原因')
    return false
  }
  revoking.value = true
  try {
    const res = await revokeRechargeRecord(target.id, {
      reason: revokeReason.value.trim(),
      force: revokeForce.value,
    })
    Message.success(res.data?.message || '已撤销充值记录')
    revokeVisible.value = false
    emit('revoked', target.customer_id)
    await loadRechargeRecords()
    return true
  } catch (error) {
    handleError(error, '撤销失败')
    return false
  } finally {
    revoking.value = false
  }
}

const loadRechargeRecords = async () => {
  if (!props.customerId) return
  rechargeLoading.value = true
  try {
    const res = await getRechargeRecords({
      customer_id: props.customerId,
      page: rechargePagination.current,
      page_size: rechargePagination.pageSize,
    })
    rechargeRecords.value = res.data?.list || []
  } catch {
    rechargeRecords.value = []
  } finally {
    rechargeLoading.value = false
  }
}

const handleRechargePageChange = (page: number) => {
  rechargePagination.current = page
  loadRechargeRecords()
}

// ===== 消耗记录 =====
const consumptionLoading = ref(false)
const consumptionRecords = ref<ConsumptionRecord[]>([])
const consumptionPagination = reactive({ current: 1, pageSize: 10, showTotal: true })

const consumptionColumns = [
  { title: '消耗金额', slotName: 'amount', width: 200 },
  { title: '扣款后余额', slotName: 'balance_after', width: 150 },
  { title: '实际结算客户', slotName: 'actual_customer', width: 200 },
  { title: '关联结算单', slotName: 'invoice_no', width: 180 },
  { title: '消耗时间', slotName: 'consumed_at', width: 180 },
]

const loadConsumptionRecords = async () => {
  if (!props.customerId) return
  consumptionLoading.value = true
  try {
    const res = await getConsumptionRecords({
      customer_id: props.customerId,
      page: consumptionPagination.current,
      page_size: consumptionPagination.pageSize,
    })
    consumptionRecords.value = res.data?.list || []
  } catch {
    consumptionRecords.value = []
  } finally {
    consumptionLoading.value = false
  }
}

const handleConsumptionPageChange = (page: number) => {
  consumptionPagination.current = page
  loadConsumptionRecords()
}

// ===== Tab 切换 =====
const handleTabChange = (key: string | number) => {
  if (key === 'consumption' && consumptionRecords.value.length === 0) {
    loadConsumptionRecords()
  }
}

// ===== 弹窗打开时加载 =====
watch(
  () => props.visible,
  (val) => {
    if (val) {
      activeTab.value = 'recharge'
      rechargePagination.current = 1
      consumptionPagination.current = 1
      consumptionRecords.value = []
      loadRechargeRecords()
    }
  }
)
</script>

<style scoped>
.amount-detail {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
  display: flex;
  gap: 10px;
  white-space: nowrap;
}
.amount-detail .real {
  color: var(--primary);
}
.amount-detail .bonus {
  color: var(--green);
}

.consumption-amount {
  color: var(--red, #dc2626);
  font-weight: 600;
}

.balance-after {
  color: var(--primary);
  font-weight: 500;
}

.customer-id {
  color: var(--muted);
  font-size: 12px;
}

.invoice-link {
  color: var(--primary);
  text-decoration: underline;
  cursor: pointer;
}

.invoice-link:hover {
  opacity: 0.8;
}

.btn-revoke {
  border-color: var(--red, #dc2626);
  color: var(--red, #dc2626);
}

.btn-revoke:hover {
  background: rgba(220, 38, 38, 0.08);
}

.subtle {
  color: var(--muted);
}

.revoke-body .revoke-row {
  display: flex;
  gap: 12px;
  padding: 4px 0;
  font-size: 13px;
}

.revoke-body .revoke-row .label {
  width: 84px;
  flex-shrink: 0;
  color: var(--muted);
}

.revoke-body .amount-strong {
  color: var(--primary);
  font-weight: 600;
}

.revoke-tip {
  margin-top: 12px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.6;
}

.source-crm {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  background: rgba(37, 99, 235, 0.1);
  color: var(--primary, #2563eb);
  white-space: nowrap;
}
</style>
