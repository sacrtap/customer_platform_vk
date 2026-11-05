<template>
  <div class="vr-settlement-page">
    <!-- PageHeader -->
    <PageHeader
      eyebrow="Billing"
      title="VR编辑费用结算"
      subtitle="VR编辑费用结算单列表、详情查看与状态流转"
    >
      <template #actions>
        <button
          v-if="can('vr_settlement:create')"
          class="btn primary"
          @click="createModalVisible = true"
        >
          创建结算单
        </button>
      </template>
    </PageHeader>

    <!-- 筛选 + 表格 在同一卡片内 -->
    <div class="card pad main-card">
      <!-- 筛选行（内联，不建 Filters 组件） -->
      <div class="filters">
        <a-input
          v-model="filters.keyword"
          placeholder="结算单号 / 客户名称，回车搜索"
          allow-clear
          style="width: 240px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <FilterDropdown
          v-model="filters.status"
          label="状态"
          :options="VR_SETTLEMENT_STATUS_OPTIONS"
          @apply="handleSearch"
        />
        <CustomerAutoComplete
          v-model="filters.customer_id"
          placeholder="客户（搜索选择）"
          :width="200"
        />
        <button type="button" class="btn primary" @click="handleSearch">查询</button>
        <button type="button" class="btn" @click="handleReset">重置</button>
      </div>

      <!-- 表格 -->
      <DataTable
        :columns="tableColumns"
        :data="settlements as unknown as Record<string, unknown>[]"
        :loading="loading"
        :pagination="paginationConfig"
        :row-key="'id'"
        :row-class="'row-clickable'"
        :scroll="{ x: 1440 }"
        :storage-key="STORAGE_KEY"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
        @sorter-change="onSorterChange"
        @row-click="onRowClick"
      >
        <template #settlement_no="{ record }">
          <span class="settlement-no">{{ (record as VrSettlement).settlement_no }}</span>
        </template>

        <template #customer_name="{ record }">
          <span class="cust-name">{{
            (record as VrSettlement).customer_name || `#${(record as VrSettlement).customer_id}`
          }}</span>
        </template>

        <template #period="{ record }">
          <span class="cell-nowrap"
            >{{ formatDate((record as VrSettlement).period_start) }} ~
            {{ formatDate((record as VrSettlement).period_end) }}</span
          >
        </template>

        <template #total_amount="{ record }">
          <span class="amount">{{ formatCurrency((record as VrSettlement).total_amount) }}</span>
        </template>

        <template #discount_amount="{ record }">
          <span
            v-if="
              (record as VrSettlement).discount_amount &&
              (record as VrSettlement).discount_amount !== 0
            "
            :class="[
              'amount',
              ((record as VrSettlement).discount_amount ?? 0) > 0 ? 'text-danger' : 'text-success',
            ]"
          >
            {{ ((record as VrSettlement).discount_amount ?? 0) > 0 ? '-' : '+'
            }}{{ formatCurrency(Math.abs((record as VrSettlement).discount_amount!)) }}
          </span>
          <span v-else class="subtle">-</span>
        </template>

        <template #final_amount="{ record }">
          <span class="amount-final">{{
            formatCurrency((record as VrSettlement).final_amount)
          }}</span>
        </template>

        <template #detail_file="{ record }">
          <span v-if="(record as VrSettlement).detail_file_path" title="明细文件已生成">📄</span>
          <span v-else class="subtle">-</span>
        </template>

        <template #status="{ record }">
          <span class="tag" :class="getVrSettlementStatusColor((record as VrSettlement).status)">
            {{ getVrSettlementStatusLabel((record as VrSettlement).status) }}
          </span>
        </template>

        <template #created_at="{ record }">
          <span class="cell-nowrap">{{ formatDateTime((record as VrSettlement).created_at) }}</span>
        </template>

        <template #action="{ record }">
          <!-- 提交（草稿） -->
          <button
            v-if="(record as VrSettlement).status === 'draft' && can('vr_settlement:create')"
            class="btn btn-primary-sm"
            style="padding: 4px 10px; font-size: 12px"
            @click.stop="handleSingleAction(record as VrSettlement, 'submit')"
          >
            提交
          </button>
          <!-- 设置/修改减免入口在详情抽屉（VrSettlementDetailDrawer edit-discount），
               操作列不再放置，避免与审批按钮争位 -->
          <!-- 客服主管审批 -->
          <button
            v-if="
              can('vr_settlement:cs_approve') &&
              (record as VrSettlement).status === 'pending_cs_supervisor'
            "
            class="btn btn-primary-sm"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            @click.stop="handleSingleAction(record as VrSettlement, 'confirm-cs')"
          >
            客服主管审批
          </button>
          <button
            v-if="
              can('vr_settlement:cs_approve') &&
              (record as VrSettlement).status === 'pending_cs_supervisor'
            "
            class="btn"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            @click.stop="handleSingleAction(record as VrSettlement, 'rollback')"
          >
            回退
          </button>
          <!-- 销售审批（需为该客户指定销售） -->
          <button
            v-if="
              can('vr_settlement:sales_approve') &&
              (record as VrSettlement).status === 'pending_sales'
            "
            class="btn btn-primary-sm"
            :style="{
              padding: '4px 10px',
              fontSize: '12px',
              marginLeft: '4px',
              opacity: canConfirmSales(record as VrSettlement) ? 1 : 0.5,
              cursor: canConfirmSales(record as VrSettlement) ? 'pointer' : 'not-allowed',
            }"
            :disabled="!canConfirmSales(record as VrSettlement)"
            :title="
              canConfirmSales(record as VrSettlement)
                ? ''
                : salesDisabledTip(record as VrSettlement)
            "
            @click.stop="
              canConfirmSales(record as VrSettlement) &&
              handleSingleAction(record as VrSettlement, 'confirm-sales')
            "
          >
            销售审批
          </button>
          <button
            v-if="
              can('vr_settlement:sales_approve') &&
              (record as VrSettlement).status === 'pending_sales' &&
              canConfirmSales(record as VrSettlement)
            "
            class="btn"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            @click.stop="handleSingleAction(record as VrSettlement, 'rollback')"
          >
            回退
          </button>
          <!-- 销售主管审批通过 / 驳回 -->
          <button
            v-if="
              can('vr_settlement:sales_supervisor_approve') &&
              (record as VrSettlement).status === 'pending_sales_supervisor'
            "
            class="btn btn-primary-sm"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            :disabled="discountApprovalBlocked(record as VrSettlement)"
            :title="discountApprovalBlocked(record as VrSettlement) ? discountApprovalTip : ''"
            @click.stop="openApprovalModal(record as VrSettlement, 'approve')"
          >
            审批通过
          </button>
          <button
            v-if="
              can('vr_settlement:sales_supervisor_approve') &&
              (record as VrSettlement).status === 'pending_sales_supervisor'
            "
            class="btn"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            @click.stop="openApprovalModal(record as VrSettlement, 'reject')"
          >
            审批驳回
          </button>
          <!-- 客户确认（需为该客户指定销售，与后端 confirm_customer 同源） -->
          <button
            v-if="
              can('vr_settlement:confirm') && (record as VrSettlement).status === 'pending_customer'
            "
            class="btn btn-primary-sm"
            :style="{
              padding: '4px 10px',
              fontSize: '12px',
              marginLeft: '4px',
              opacity: canConfirmSales(record as VrSettlement) ? 1 : 0.5,
              cursor: canConfirmSales(record as VrSettlement) ? 'pointer' : 'not-allowed',
            }"
            :disabled="!canConfirmSales(record as VrSettlement)"
            :title="
              canConfirmSales(record as VrSettlement)
                ? ''
                : salesDisabledTip(record as VrSettlement)
            "
            @click.stop="
              canConfirmSales(record as VrSettlement) &&
              handleSingleAction(record as VrSettlement, 'confirm')
            "
          >
            客户确认
          </button>
          <!-- 重试扣款 -->
          <button
            v-if="
              can('vr_settlement:confirm') &&
              (record as VrSettlement).status === 'customer_confirmed'
            "
            class="btn btn-primary-sm"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            :disabled="retryingId === (record as VrSettlement).id"
            @click.stop="handleSingleAction(record as VrSettlement, 'retry-deduction')"
          >
            {{ retryingId === (record as VrSettlement).id ? '扣款中...' : '重试扣款' }}
          </button>
          <!-- 取消（非终态） -->
          <button
            v-if="
              can('vr_settlement:edit') &&
              [
                'draft',
                'pending_cs_supervisor',
                'pending_sales',
                'pending_sales_supervisor',
                'pending_customer',
              ].includes((record as VrSettlement).status)
            "
            class="btn"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            @click.stop="handleSingleAction(record as VrSettlement, 'cancel')"
          >
            取消
          </button>
          <!-- 删除（草稿） -->
          <button
            v-if="can('vr_settlement:delete') && (record as VrSettlement).status === 'draft'"
            class="btn btn-danger"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            @click.stop="handleSingleAction(record as VrSettlement, 'delete')"
          >
            删除
          </button>
        </template>
      </DataTable>
    </div>

    <!-- VR 结算单详情抽屉 -->
    <VrSettlementDetailDrawer
      v-model:visible="drawerVisible"
      :settlement="currentDetail"
      @submit="handleSingleAction(currentDetail!, 'submit')"
      @confirm-cs="handleSingleAction(currentDetail!, 'confirm-cs')"
      @confirm-sales="handleSingleAction(currentDetail!, 'confirm-sales')"
      @rollback="handleSingleAction(currentDetail!, 'rollback')"
      @approve="openApprovalModal(currentDetail!, 'approve')"
      @reject="openApprovalModal(currentDetail!, 'reject')"
      @confirm="handleSingleAction(currentDetail!, 'confirm')"
      @retry-deduction="handleSingleAction(currentDetail!, 'retry-deduction')"
      @cancel="handleSingleAction(currentDetail!, 'cancel')"
      @delete="handleSingleAction(currentDetail!, 'delete')"
      @edit-discount="openDiscountModal(currentDetail!)"
    />
    <!-- 创建结算单弹窗 -->
    <VrSettlementCreateModal v-model:visible="createModalVisible" @success="handleCreateSuccess" />
    <!-- 修改减免弹窗 -->
    <VrSettlementDiscountModal
      v-model:visible="discountModalVisible"
      :settlement-id="selectedSettlementId"
      :current-discount="currentDetail?.discount_amount"
      :current-reason="currentDetail?.discount_reason"
      :current-attachment="currentDetail?.discount_attachment"
      @success="handleDiscountSuccess"
    />
    <!-- 销售主管审批弹窗（通过可选理由 / 驳回必填理由） -->
    <VrSettlementApprovalModal
      v-model:visible="approvalModalVisible"
      :settlement-id="approvalSettlementId"
      :mode="approvalMode"
      :discount-amount="approvalDiscountAmount"
      :discount-reason="approvalDiscountReason"
      @success="handleApprovalSuccess"
    />
    <!-- 回退弹窗（审批节点回退至上一步，理由必填） -->
    <RollbackModal
      v-model:visible="rollbackModalVisible"
      :loading="rollbackSubmitting"
      title="回退至上一步审核"
      @submit="handleRollbackSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Modal } from '@arco-design/web-vue'
import PageHeader from '@/components/PageHeader.vue'
import DataTable, { type DataTableColumn } from '@/components/DataTable.vue'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
import { useUserStore } from '@/stores/user'
import { useVrSettlement } from '@/composables/useVrSettlement'
import { formatCurrency, formatDate, formatDateTime } from '@/utils/formatters'
import {
  VR_SETTLEMENT_STATUS_OPTIONS,
  getVrSettlementStatusColor,
  getVrSettlementStatusLabel,
} from '@/constants/vrSettlementStatus'
import type { VrSettlement } from '@/api/vrSettlement'
import VrSettlementDetailDrawer from './components/VrSettlementDetailDrawer.vue'
import VrSettlementCreateModal from './components/VrSettlementCreateModal.vue'
import VrSettlementDiscountModal from './components/VrSettlementDiscountModal.vue'
import VrSettlementApprovalModal from './components/VrSettlementApprovalModal.vue'
import RollbackModal from './components/RollbackModal.vue'

const userStore = useUserStore()
const can = (p: string) => userStore.hasPermission(p)
const currentUserId = computed(() => userStore.userInfo?.id)

// ===== 经理身份校验：仅该客户指定的销售可点击「销售审批」「客户确认」=====
// 超级管理员若非该客户指定销售，同样不可操作（与后端校验保持一致）
const canConfirmSales = (record: VrSettlement) =>
  currentUserId.value === record.customer_sales_manager_id

// 禁用时的 hover 提示文案
const salesDisabledTip = (record: VrSettlement) =>
  !record.customer_sales_manager_id
    ? '该客户尚未指定销售，无法确认'
    : '您不是该客户指定的销售，无法确认'

// ===== 减免审批门禁（与详情抽屉、后端 confirm_sales_supervisor 同源）=====
// discount_approval_required 由列表接口按「有减免且系统存在持权用户」实时计算
const discountApprovalBlocked = (record: VrSettlement) =>
  record.discount_approval_required === true && !can('billing:discount_approve')
const discountApprovalTip = '该结算单包含减免，需由具有减免审批权限的用户审批'

const {
  loading,
  settlements,
  total,
  currentDetail,
  filters,
  pagination,
  loadVrSettlements,
  fetchVrDetail,
  handlePageChange,
  handlePageSizeChange,
  handleSortChange,
  handleSearch,
  handleReset,
  doSubmit,
  doConfirmCs,
  doConfirmSales,
  doRollback,
  doConfirm,
  doRetryDeduction,
  doCancel,
  doDelete,
} = useVrSettlement()

const drawerVisible = ref(false)
const createModalVisible = ref(false)
const discountModalVisible = ref(false)
const selectedSettlementId = ref<number>(0)
const retryingId = ref<number | null>(null)

// ===== 销售主管审批弹窗 =====
const approvalModalVisible = ref(false)
const approvalMode = ref<'approve' | 'reject'>('approve')
const approvalSettlementId = ref<number>(0)
const approvalDiscountAmount = ref<number | undefined>(undefined)
const approvalDiscountReason = ref<string | undefined>(undefined)

// --- 列定义（含操作列固定右侧） ---
const STORAGE_KEY = 'vr_settlements_table_columns'

interface ColumnDef {
  key: string
  title: string
  width?: number
  align?: 'left' | 'center' | 'right'
  sortable?: boolean
  ellipsis?: boolean
  tooltip?: boolean
}

const columnDefs: ColumnDef[] = [
  { key: 'settlement_no', title: '结算单号', width: 214, sortable: true },
  { key: 'customer_name', title: '客户', width: 180, ellipsis: true, tooltip: true },
  { key: 'period', title: '周期', width: 190 },
  { key: 'total_amount', title: '总金额', width: 104, align: 'right', sortable: true },
  { key: 'discount_amount', title: '减免金额', width: 76, align: 'right' },
  { key: 'final_amount', title: '最终结算金额', width: 110, align: 'right' },
  { key: 'detail_file', title: '文件', width: 108, align: 'center' },
  { key: 'status', title: '状态', width: 78 },
  { key: 'created_at', title: '创建时间', width: 158, sortable: true },
]

const tableColumns = computed<DataTableColumn[]>(() => [
  ...columnDefs.map((col) => ({
    key: col.key,
    title: col.title,
    width: col.width,
    align: col.align,
    ellipsis: col.ellipsis,
    tooltip: col.tooltip,
    sortable: col.sortable
      ? { sortDirections: ['ascend', 'descend'] as ('ascend' | 'descend')[] }
      : undefined,
  })),
  { key: 'action', title: '操作', slotName: 'action', fixed: 'right' as const, width: 174 },
])

// --- 分页配置：透传给 a-table 内置分页 ---
const paginationConfig = computed(() => ({
  current: pagination.current,
  pageSize: pagination.pageSize,
  total: total.value,
  showTotal: true,
  showPageSize: true,
  showJumper: true,
  pageSizeOptions: [10, 20, 50, 100],
}))

// --- 排序：a-table 三态；清除时 emit 空字符串以便 composable 清除排序状态 ---
// 方向词表 ascend/descend → asc/desc 必须在此转换（与 Invoices.vue 同一修复模式）
const onSorterChange = (dataIndex: string, direction: string) => {
  const order = direction === 'ascend' ? 'asc' : direction === 'descend' ? 'desc' : ''
  handleSortChange(order ? dataIndex : '', order)
}

const onPageChange = (page: number) => {
  handlePageChange(page)
}

const onPageSizeChange = (size: number) => {
  handlePageSizeChange(size)
}

// --- 行点击进详情 ---
const onRowClick = (record: unknown) => {
  viewSettlement(record as VrSettlement)
}

const viewSettlement = async (record: VrSettlement) => {
  await fetchVrDetail(record.id)
  drawerVisible.value = true
}

// --- 弹窗开关 ---
const openDiscountModal = (record: VrSettlement) => {
  selectedSettlementId.value = record.id
  discountModalVisible.value = true
}

const openApprovalModal = (record: VrSettlement, mode: 'approve' | 'reject') => {
  approvalMode.value = mode
  approvalSettlementId.value = record.id
  // 有待审批减免时展示在弹窗顶部（只读）
  approvalDiscountAmount.value = record.discount_amount || undefined
  approvalDiscountReason.value = record.discount_reason || undefined
  approvalModalVisible.value = true
}

const handleCreateSuccess = () => {
  createModalVisible.value = false
  loadVrSettlements()
}

const handleDiscountSuccess = async () => {
  discountModalVisible.value = false
  loadVrSettlements()
  if (drawerVisible.value && currentDetail.value) {
    await fetchVrDetail(currentDetail.value.id)
  }
}

const handleApprovalSuccess = async () => {
  approvalModalVisible.value = false
  loadVrSettlements()
  if (drawerVisible.value && currentDetail.value) {
    await fetchVrDetail(currentDetail.value.id)
  }
}

// ===== 回退弹窗（各内部审批节点回退至上一步，理由必填） =====
const rollbackModalVisible = ref(false)
const rollbackTarget = ref<VrSettlement | null>(null)
const rollbackSubmitting = ref(false)

const openRollbackModal = (record: VrSettlement) => {
  rollbackTarget.value = record
  rollbackModalVisible.value = true
}

const handleRollbackSubmit = async (comment: string) => {
  if (!rollbackTarget.value) return
  rollbackSubmitting.value = true
  try {
    await doRollback(rollbackTarget.value.id, comment)
    rollbackModalVisible.value = false
    if (drawerVisible.value && rollbackTarget.value) {
      await fetchVrDetail(rollbackTarget.value.id)
    }
  } catch {
    // 错误消息已由 useVrSettlement 的 Message.error 统一处理
  } finally {
    rollbackSubmitting.value = false
  }
}

// --- 单条操作（提交/客服主管/销售/回退/客户确认/重试扣款/取消/删除） ---
const handleSingleAction = async (
  record: VrSettlement,
  action:
    | 'submit'
    | 'confirm-cs'
    | 'confirm-sales'
    | 'rollback'
    | 'confirm'
    | 'retry-deduction'
    | 'cancel'
    | 'delete'
) => {
  const refreshDetailIfOpen = async () => {
    if (drawerVisible.value && record.id) {
      await fetchVrDetail(record.id)
    }
  }

  const actions: Record<string, () => Promise<void> | void> = {
    submit: async () => {
      await doSubmit(record.id)
      await refreshDetailIfOpen()
    },
    'confirm-cs': async () => {
      await doConfirmCs(record.id)
      await refreshDetailIfOpen()
    },
    'confirm-sales': async () => {
      await doConfirmSales(record.id)
      await refreshDetailIfOpen()
    },
    rollback: () => {
      openRollbackModal(record)
    },
    confirm: async () => {
      await doConfirm(record.id)
      await refreshDetailIfOpen()
    },
    'retry-deduction': () => {
      Modal.confirm({
        title: '确认重试扣款',
        content: `确定要对结算单「${record.settlement_no}」重新执行扣款吗？将扣除金额 ${formatCurrency(record.final_amount)}。`,
        onOk: async () => {
          retryingId.value = record.id
          try {
            await doRetryDeduction(record.id)
            await refreshDetailIfOpen()
          } catch {
            // 错误消息已由 composable 处理
          } finally {
            retryingId.value = null
          }
        },
      })
    },
    cancel: () => {
      Modal.confirm({
        title: '确认取消',
        content: '确定要取消该结算单吗？',
        onOk: async () => {
          await doCancel(record.id)
          await refreshDetailIfOpen()
        },
      })
    },
    delete: () => {
      Modal.confirm({
        title: '确认删除',
        content: '确定要删除该结算单吗？此操作不可恢复。',
        onOk: async () => {
          await doDelete(record.id)
          if (drawerVisible.value) drawerVisible.value = false
        },
      })
    },
  }
  await Promise.resolve(actions[action]()).catch(() => {
    // 各 action 内部已有错误处理；此处 catch 防止未处理的 Promise 拒绝
  })
}

// 初始化
loadVrSettlements()

// 支持 URL query highlight 参数自动打开结算单详情
onMounted(async () => {
  const highlightId = window.location.search
    ? new URLSearchParams(window.location.search).get('highlight')
    : null
  if (highlightId) {
    const id = Number(highlightId)
    if (id > 0) {
      await fetchVrDetail(id)
      drawerVisible.value = true
    }
  }
})
</script>

<style scoped>
.vr-settlement-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 1440px;
  margin: 0 auto;
}

/* 覆盖 PageHeader 的 margin-bottom，使用 gap 控制间距 */
.vr-settlement-page :deep(.page-header) {
  margin-bottom: 0;
}

/* 筛选行（内联） */
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

/* 按钮样式（与 Invoices.vue 一致） */
.btn {
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  border-radius: 12px;
  padding: 9px 12px;
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
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}
.btn.primary:hover {
  background: #1e40af;
}
.btn.btn-primary-sm {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}
.btn.btn-primary-sm:hover {
  background: #1e40af;
}
.btn.btn-danger {
  color: var(--red);
  border-color: #fecaca;
}
.btn.btn-danger:hover {
  background: #fef2f2;
  border-color: #fca5a5;
}

/* 结算单号 */
.settlement-no {
  font-variant-numeric: tabular-nums;
  color: var(--ink);
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
}

/* 客户名称 */
.cust-name {
  font-weight: 600;
  color: var(--ink);
}

/* 金额 */
.amount {
  font-weight: 500;
  color: var(--ink);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.amount-final {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.text-danger {
  color: var(--red);
  white-space: nowrap;
}
.text-success {
  color: var(--green, #10b981);
  white-space: nowrap;
}
.cell-nowrap {
  white-space: nowrap;
}

/* 行点击进详情：指针样式（DataTable 行高亮由组件内置） */
:deep(.arco-table-tr.row-clickable) {
  cursor: pointer;
}
</style>
