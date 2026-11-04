<template>
  <a-drawer
    v-model:visible="isVisible"
    title="VR结算单详情"
    width="720px"
    unmount-on-close
    :footer="false"
  >
    <template v-if="settlement">
      <div class="drawer-content">
        <div class="detail-header">
          <div class="detail-title">
            <h2>{{ settlement.settlement_no }}</h2>
            <span class="tag" :class="getVrSettlementStatusColor(settlement.status)">
              {{ getVrSettlementStatusLabel(settlement.status) }}
            </span>
          </div>
        </div>

        <!-- 审批流程状态条（6 步） -->
        <div v-if="settlement.status !== 'cancelled'" class="flow-steps">
          <a-steps :current="flowStepIndex" size="small" :status="flowStepsStatus">
            <a-step title="创建" :description="settlement.created_by_name || undefined" />
            <a-step
              title="客服主管审批"
              :description="settlement.cs_supervisor_confirmed_name || undefined"
            />
            <a-step title="销售审批" :description="settlement.sales_confirmed_name || undefined" />
            <a-step
              title="销售主管审批"
              :description="settlement.sales_supervisor_confirmed_name || undefined"
            />
            <a-step
              title="客户确认"
              :description="settlement.customer_confirmed_name || undefined"
            />
            <!-- 客户确认后由后端自动扣款（confirm_customer → _execute_deduction），
                 成功即 completed，故「客户确认」与「结算」合并为末步「已完成」 -->
            <a-step title="已完成" :description="flowSettledDescription || undefined" />
          </a-steps>
        </div>
        <div v-else class="flow-steps flow-cancelled">
          <a-steps :current="0" size="small" status="error">
            <a-step title="已取消" :description="settlement.cancelled_name || undefined" />
          </a-steps>
        </div>

        <a-descriptions :column="2" bordered size="small" class="detail-info">
          <a-descriptions-item label="客户名称">
            {{ settlement.customer_name || `#${settlement.customer_id}` }}
          </a-descriptions-item>
          <a-descriptions-item label="结算周期">
            {{ formatDate(settlement.period_start) }} ~ {{ formatDate(settlement.period_end) }}
          </a-descriptions-item>
          <a-descriptions-item label="总金额">{{
            formatCurrency(settlement.total_amount)
          }}</a-descriptions-item>
          <a-descriptions-item label="减免金额">
            <span
              v-if="settlement.discount_amount && settlement.discount_amount !== 0"
              :class="settlement.discount_amount > 0 ? 'text-danger' : 'text-success'"
            >
              {{ settlement.discount_amount > 0 ? '-' : '+'
              }}{{ formatCurrency(Math.abs(settlement.discount_amount)) }}
            </span>
            <span v-else class="subtle">无减免</span>
          </a-descriptions-item>
          <a-descriptions-item
            v-if="
              settlement.discount_reason ||
              (settlement.discount_amount && settlement.discount_amount !== 0)
            "
            label="减免说明"
            :span="2"
            >{{ settlement.discount_reason || '—' }}</a-descriptions-item
          >
          <a-descriptions-item v-if="settlement.discount_attachment" label="减免附件" :span="2">
            <a
              :href="settlement.discount_attachment"
              target="_blank"
              download
              class="attachment-link"
              >查看附件</a
            >
          </a-descriptions-item>
          <!-- 减免审批结果（销售主管一并审批） -->
          <template v-if="settlement.discount_amount && settlement.discount_amount !== 0">
            <a-descriptions-item label="减免审批人">
              {{ settlement.discount_approver_name || '—' }}
            </a-descriptions-item>
            <a-descriptions-item label="减免审批时间">
              {{ formatDateTime(settlement.discount_approved_at) }}
            </a-descriptions-item>
            <a-descriptions-item
              v-if="settlement.discount_approval_comment"
              label="审批意见"
              :span="2"
              >{{ settlement.discount_approval_comment }}</a-descriptions-item
            >
          </template>
          <a-descriptions-item label="最终结算金额">
            <span class="amount-final">{{ formatCurrency(settlement.final_amount) }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="创建时间">
            {{ formatDateTime(settlement.created_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="明细文件">
            <!-- 与结算单管理详情同一交互：状态文本 + 「下载明细」按钮，样式共用 detail-drawer.css -->
            <div class="detail-file-section">
              <span v-if="settlement.detail_file_path" class="file-status completed"
                >✅ 已生成</span
              >
              <span v-else class="file-status pending">— 无明细文件</span>
              <button
                v-if="can('vr_settlement:view') && settlement.detail_file_path"
                class="btn btn-sm"
                @click="handleDownloadDetail"
              >
                下载明细
              </button>
            </div>
          </a-descriptions-item>
          <a-descriptions-item v-if="settlement.remark" label="备注说明" :span="2">
            <span class="remark-text">{{ settlement.remark }}</span>
          </a-descriptions-item>
        </a-descriptions>

        <!-- 减免修改历史（与结算单管理详情共用 DiscountHistoryTable，标题与外框由组件自带） -->
        <DiscountHistoryTable
          v-if="settlement.discount_history && settlement.discount_history.length > 0"
          :histories="settlement.discount_history"
        />

        <!-- 操作记录：状态流转时间线（创建→客服主管→销售→销售主管→客户确认→完成/取消） -->
        <div class="detail-section">
          <div class="section-header"><h3>操作记录</h3></div>
          <VrSettlementTimeline :settlement="settlement" />
        </div>

        <div class="action-section">
          <button
            v-if="can('vr_settlement:create') && settlement.status === 'draft'"
            class="btn primary"
            @click="emit('submit', settlement.id)"
          >
            提交
          </button>
          <!-- 设置/修改减免：销售主管审批通过前的任意节点可改（含 pending_sales_supervisor）；
               客户确认后锁定（减免已随销售主管一并审批生效） -->
          <button
            v-if="
              can('vr_settlement:discount_apply') &&
              [
                'draft',
                'pending_cs_supervisor',
                'pending_sales',
                'pending_sales_supervisor',
              ].includes(settlement.status)
            "
            class="btn"
            @click="emit('edit-discount', settlement.id)"
          >
            {{ settlement.discount_amount ? '修改减免' : '设置减免' }}
          </button>
          <!-- 客服主管审批 -->
          <button
            v-if="can('vr_settlement:cs_approve') && settlement.status === 'pending_cs_supervisor'"
            class="btn primary"
            @click="emit('confirm-cs', settlement.id)"
          >
            客服主管审批
          </button>
          <!-- 回退至上一步：pending_cs_supervisor → draft（与审批同权限，无身份校验） -->
          <button
            v-if="can('vr_settlement:cs_approve') && settlement.status === 'pending_cs_supervisor'"
            class="btn"
            @click="emit('rollback', settlement.id)"
          >
            回退
          </button>
          <!-- 销售审批：非指定销售时禁用并提示 -->
          <template
            v-if="can('vr_settlement:sales_approve') && settlement.status === 'pending_sales'"
          >
            <button
              v-if="canConfirmSales"
              class="btn primary"
              @click="emit('confirm-sales', settlement.id)"
            >
              销售审批
            </button>
            <a-tooltip v-else :content="salesDisabledTip" position="top">
              <span class="btn primary disabled">销售审批</span>
            </a-tooltip>
            <!-- 回退至上一步：pending_sales → pending_cs_supervisor（与审批同权限 + 同身份校验） -->
            <button v-if="canConfirmSales" class="btn" @click="emit('rollback', settlement.id)">
              回退
            </button>
          </template>
          <!-- 销售主管审批（含减免一并审批） -->
          <template
            v-if="
              can('vr_settlement:sales_supervisor_approve') &&
              settlement.status === 'pending_sales_supervisor'
            "
          >
            <!-- 减免审批门禁：有减免且系统存在持权用户时，无减免审批权限禁用通过（驳回不受限） -->
            <button
              v-if="!discountApprovalBlocked"
              class="btn primary"
              @click="emit('approve', settlement.id)"
            >
              审批通过
            </button>
            <a-tooltip v-else :content="discountApprovalTip" position="top">
              <span class="btn primary disabled">审批通过</span>
            </a-tooltip>
            <button class="btn btn-danger" @click="emit('reject', settlement.id)">审批驳回</button>
          </template>
          <button
            v-if="can('vr_settlement:confirm') && settlement.status === 'pending_customer'"
            class="btn primary"
            @click="emit('confirm', settlement.id)"
          >
            客户确认
          </button>
          <button
            v-if="can('vr_settlement:confirm') && settlement.status === 'customer_confirmed'"
            class="btn primary"
            :disabled="retrying"
            @click="emit('retry-deduction', settlement.id)"
          >
            {{ retrying ? '扣款中...' : '重试扣款' }}
          </button>
          <button
            v-if="
              can('vr_settlement:edit') &&
              [
                'draft',
                'pending_cs_supervisor',
                'pending_sales',
                'pending_sales_supervisor',
                'pending_customer',
              ].includes(settlement.status)
            "
            class="btn btn-danger"
            @click="emit('cancel', settlement.id)"
          >
            取消结算单
          </button>
          <button
            v-if="can('vr_settlement:delete') && settlement.status === 'draft'"
            class="btn btn-danger"
            @click="emit('delete', settlement.id)"
          >
            删除
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
import { formatCurrency, formatDate, formatDateTime } from '@/utils/formatters'
import {
  getVrSettlementStatusColor,
  getVrSettlementStatusLabel,
} from '@/constants/vrSettlementStatus'
import type { VrSettlement } from '@/api/vrSettlement'
import VrSettlementTimeline from '@/components/vr/VrSettlementTimeline.vue'
import DiscountHistoryTable from '@/components/common/DiscountHistoryTable.vue'

const props = defineProps<{
  visible: boolean
  settlement?: VrSettlement | null
  retrying?: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [id: number]
  'confirm-cs': [id: number]
  'confirm-sales': [id: number]
  rollback: [id: number]
  approve: [id: number]
  reject: [id: number]
  confirm: [id: number]
  'retry-deduction': [id: number]
  cancel: [id: number]
  delete: [id: number]
  'edit-discount': [id: number]
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const userStore = useUserStore()
const can = (p: string) => userStore.hasPermission(p)
const currentUserId = computed(() => userStore.userInfo?.id)

// ===== 明细文件下载（与结算单管理详情同一交互：按钮触发，而非裸链接） =====
// VR 明细文件是创建时上传的静态文件（detail_file_path），无生成状态机，
// 因此只有「已生成 / 无明细文件」两态，不涉及重新生成。
const handleDownloadDetail = () => {
  const s = props.settlement
  if (!s?.detail_file_path) return
  const link = document.createElement('a')
  link.href = s.detail_file_path
  link.download = s.detail_file_name || ''
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

// ===== 销售身份校验：仅该客户指定的销售可点击「销售审批」=====
const canConfirmSales = computed(() => {
  if (!props.settlement) return false
  return currentUserId.value === props.settlement.customer_sales_manager_id
})

const salesDisabledTip = computed(() => {
  if (!props.settlement) return ''
  if (!props.settlement.customer_sales_manager_id) {
    return '该客户尚未指定销售，无法确认'
  }
  return '您不是该客户指定的销售，无法确认'
})

// ===== 减免审批门禁：后端确认有持权用户且当前结算单有减免时，
//      无减免审批权限的用户禁用「审批通过」（与后端 confirm_sales_supervisor 同源） =====
const discountApprovalBlocked = computed(
  () => props.settlement?.discount_approval_required === true && !can('billing:discount_approve')
)
const discountApprovalTip = '该结算单包含减免，需由具有减免审批权限的用户审批'

// ===== 审批流程状态条（6 步）=====
// 注意：Arco Steps 的 current 是 1-based 步号（与 InvoiceDetailDrawer 同一约定）。
// customer_confirmed = 客户已确认但自动扣款失败/进行中：末步标红提示需重试扣款。
const STATUS_TO_STEP: Record<string, number> = {
  draft: 1,
  pending_cs_supervisor: 2,
  pending_sales: 3,
  pending_sales_supervisor: 4,
  pending_customer: 5,
  customer_confirmed: 6,
  completed: 6,
  cancelled: 1,
}
const flowStepIndex = computed(() => {
  if (!props.settlement) return 1
  return STATUS_TO_STEP[props.settlement.status] ?? 1
})

const flowStepsStatus = computed(() =>
  props.settlement?.status === 'customer_confirmed' ? 'error' : 'process'
)
const flowSettledDescription = computed(() =>
  props.settlement?.status === 'customer_confirmed' ? '扣款失败，待重试' : undefined
)
</script>

<style scoped>
/* 抽屉级公共样式与结算单详情共用单一来源，避免两份定义漂移 */
@import '@/styles/detail-drawer.css';

/* Arco steps 默认字号偏大，720px 抽屉内多步的 description（人名）会截断/换行 */
.flow-steps :deep(.arco-steps) {
  padding: 4px 0;
}
.flow-steps :deep(.arco-steps-item-title) {
  font-size: 13px;
}
.flow-steps :deep(.arco-steps-item-description) {
  font-size: 12px;
  max-width: 100px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* 备注说明（VR 结算单特有字段，多行文本） */
.remark-text {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
