<template>
  <div class="invoice-page">
    <!-- PageHeader -->
    <PageHeader eyebrow="Billing" title="结算单管理" subtitle="结算单列表、详情查看与状态流转">
      <template #actions>
        <button v-if="can('billing:invoice_import')" class="btn" @click="importModalVisible = true">
          导入
        </button>
        <button
          v-if="can('billing:invoice_export')"
          class="btn"
          :disabled="exporting"
          @click="handleExport"
        >
          {{ exporting ? '导出中...' : '导出' }}
        </button>
        <button
          v-if="can('billing:detail_status_view')"
          class="btn"
          @click="detailStatusVisible = true"
        >
          明细生成状态
        </button>
        <button v-if="can('billing:edit')" class="btn primary" @click="generateModalVisible = true">
          生成结算单
        </button>
      </template>
    </PageHeader>

    <!-- 筛选 + 表格 在同一卡片内 -->
    <div class="card pad main-card">
      <!-- 筛选器 -->
      <InvoiceFilters v-model:filters="filters" @search="handleSearch" @reset="handleReset" />

      <!-- 批量操作工具栏（跨页保留选中） -->
      <div v-if="hasSelected" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedInvoiceIds.length }} 项</span>
        <div class="batch-actions">
          <button v-if="can('billing:edit')" class="btn btn-primary-sm" @click="onBatchSubmit">
            批量提交
          </button>
          <button v-if="can('billing:edit')" class="btn btn-primary-sm" @click="onBatchCancel">
            批量取消
          </button>
          <button v-if="can('billing:delete')" class="btn btn-danger-sm" @click="onBatchDelete">
            批量删除
          </button>
          <button v-if="can('billing:view')" class="btn btn-sm" @click="onBatchDownloadDetail">
            批量下载明细
          </button>
          <button class="btn btn-sm" @click="clearSelection">取消选择</button>
        </div>
      </div>

      <!-- 表格 -->
      <DataTable
        :columns="tableColumns"
        :data="invoices as unknown as Record<string, unknown>[]"
        :loading="loading"
        :pagination="paginationConfig"
        :row-key="'id'"
        :row-selection="rowSelectionConfig"
        :row-class="'row-clickable'"
        :scroll="{ x: 1410 }"
        :storage-key="STORAGE_KEY"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
        @sorter-change="onSorterChange"
        @row-click="onRowClick"
        @select="onRowSelect"
        @select-all="onSelectAll"
      >
        <template #invoice_no="{ record }">
          <span class="invoice-no">{{ (record as Invoice).invoice_no }}</span>
        </template>

        <template #customer="{ record }">
          <span class="cust-name">{{
            (record as Invoice).customer_name || `#${(record as Invoice).customer_id}`
          }}</span>
        </template>

        <template #period="{ record }">
          <span class="cell-nowrap"
            >{{ formatDate((record as Invoice).period_start) }} ~
            {{ formatDate((record as Invoice).period_end) }}</span
          >
        </template>

        <template #total_amount="{ record }">
          <span class="amount">{{ formatCurrency((record as Invoice).total_amount) }}</span>
        </template>

        <template #discount_amount="{ record }">
          <span
            v-if="(record as Invoice).discount_amount && (record as Invoice).discount_amount !== 0"
            :class="[
              'amount',
              ((record as Invoice).discount_amount ?? 0) > 0 ? 'text-danger' : 'text-success',
            ]"
          >
            {{ ((record as Invoice).discount_amount ?? 0) > 0 ? '-' : '+'
            }}{{ formatCurrency(Math.abs((record as Invoice).discount_amount!)) }}
          </span>
          <span v-else class="subtle">-</span>
        </template>

        <template #final_amount="{ record }">
          <span class="amount-final">{{ formatCurrency((record as Invoice).final_amount) }}</span>
        </template>

        <template #detail_file="{ record }">
          <span v-if="(record as Invoice).detail_file_status === 'completed'" title="明细文件已生成"
            >📄</span
          >
          <span
            v-else-if="(record as Invoice).detail_file_status === 'generating'"
            title="生成中..."
            class="subtle"
            >⏳</span
          >
          <template v-else-if="(record as Invoice).detail_file_status === 'failed'">
            <span title="生成失败" class="text-danger">❌</span>
            <button
              v-if="can('billing:edit')"
              class="btn btn-primary-sm batch-toolbar-btn"
              @click.stop="handleRegenerateDetail((record as Invoice).id)"
            >
              重新生成
            </button>
          </template>
          <template v-else-if="(record as Invoice).detail_file_status === 'pending'">
            <span title="待生成" class="subtle">⏳</span>
            <button
              v-if="can('billing:edit')"
              class="btn btn-primary-sm batch-toolbar-btn"
              @click.stop="handleRegenerateDetail((record as Invoice).id)"
            >
              重新生成
            </button>
          </template>
          <span v-else class="subtle">-</span>
        </template>

        <template #status="{ record }">
          <InvoiceStatusBadge :status="(record as Invoice).status" />
        </template>

        <template #created_at="{ record }">
          <span class="cell-nowrap">{{ formatDateTime((record as Invoice).created_at) }}</span>
        </template>

        <template #action="{ record }">
          <button
            v-if="(record as Invoice).status === 'draft'"
            class="btn btn-primary-sm"
            style="padding: 4px 10px; font-size: 12px"
            @click.stop="openSubmitModal(record as Invoice)"
          >
            提交
          </button>
          <button
            v-if="can('billing:ops_approve') && (record as Invoice).status === 'pending_ops'"
            class="btn btn-primary-sm"
            :style="{
              padding: '4px 10px',
              fontSize: '12px',
              marginLeft: '4px',
              opacity: canConfirmOps(record as Invoice) ? 1 : 0.5,
              cursor: canConfirmOps(record as Invoice) ? 'pointer' : 'not-allowed',
            }"
            :disabled="!canConfirmOps(record as Invoice)"
            :title="canConfirmOps(record as Invoice) ? '' : opsDisabledTip(record as Invoice)"
            @click.stop="
              canConfirmOps(record as Invoice) &&
              handleSingleAction(record as Invoice, 'confirm-ops')
            "
          >
            运营确认
          </button>
          <button
            v-if="can('billing:sales_approve') && (record as Invoice).status === 'pending_sales'"
            class="btn btn-primary-sm"
            :style="{
              padding: '4px 10px',
              fontSize: '12px',
              marginLeft: '4px',
              opacity: canConfirmSales(record as Invoice) ? 1 : 0.5,
              cursor: canConfirmSales(record as Invoice) ? 'pointer' : 'not-allowed',
            }"
            :disabled="!canConfirmSales(record as Invoice)"
            :title="canConfirmSales(record as Invoice) ? '' : salesDisabledTip(record as Invoice)"
            @click.stop="
              canConfirmSales(record as Invoice) &&
              handleSingleAction(record as Invoice, 'confirm-sales')
            "
          >
            销售确认
          </button>
          <button
            v-if="
              can('billing:discount_approve') &&
              (record as Invoice).status === 'pending_discount_approval'
            "
            class="btn btn-primary-sm"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            @click.stop="handleSingleAction(record as Invoice, 'approve-discount')"
          >
            审批通过
          </button>
          <button
            v-if="(record as Invoice).status === 'pending_customer'"
            class="btn btn-primary-sm"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            @click.stop="handleSingleAction(record as Invoice, 'confirm')"
          >
            客户确认
          </button>
          <button
            v-if="(record as Invoice).status === 'customer_confirmed'"
            class="btn btn-primary-sm"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            :disabled="retryingId === (record as Invoice).id"
            @click.stop="handleSingleAction(record as Invoice, 'retry-deduction')"
          >
            {{ retryingId === (record as Invoice).id ? '扣款中...' : '重试扣款' }}
          </button>
          <button
            v-if="
              [
                'draft',
                'pending_ops',
                'pending_sales',
                'pending_discount_approval',
                'pending_customer',
              ].includes((record as Invoice).status)
            "
            class="btn"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            @click.stop="handleSingleAction(record as Invoice, 'cancel')"
          >
            取消
          </button>
          <button
            v-if="can('billing:edit') && (record as Invoice).status === 'draft'"
            class="btn btn-danger"
            style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
            @click.stop="handleSingleAction(record as Invoice, 'delete')"
          >
            删除
          </button>
        </template>
      </DataTable>
    </div>

    <!-- 结算单详情抽屉 -->
    <InvoiceDetailDrawer
      v-model:visible="drawerVisible"
      :invoice="currentDetail"
      :retrying="retryingId === currentDetail?.id"
      @go-customer="goToCustomer"
      @submit="openSubmitModal(currentDetail!)"
      @edit-discount="openDiscountEditModal(currentDetail!)"
      @confirm-ops="handleSingleAction(currentDetail!, 'confirm-ops')"
      @confirm-sales="handleSingleAction(currentDetail!, 'confirm-sales')"
      @approve-discount="handleSingleAction(currentDetail!, 'approve-discount')"
      @reject-discount="handleSingleAction(currentDetail!, 'reject-discount')"
      @confirm="handleSingleAction(currentDetail!, 'confirm')"
      @retry-deduction="handleSingleAction(currentDetail!, 'retry-deduction')"
      @cancel="handleSingleAction(currentDetail!, 'cancel')"
      @regenerate-detail="handleRegenerateDetail"
      @update-settlement-account="handleUpdateSettlementAccount"
    />
    <!-- 生成结算单弹窗 -->
    <GenerateInvoiceModal v-model:visible="generateModalVisible" @success="handleGenerateSuccess" />
    <!-- 提交结算单弹窗 -->
    <SubmitModal
      v-model:visible="submitModalVisible"
      :invoice-id="selectedInvoiceId"
      @success="handleSubmitSuccess"
    />
    <!-- 修改减免弹窗 -->
    <DiscountEditModal
      v-model:visible="discountEditVisible"
      :invoice-id="selectedInvoiceId"
      :current-discount="currentDetail?.discount_amount"
      :current-reason="currentDetail?.discount_reason"
      :current-attachment="currentDetail?.discount_attachment"
      @success="handleDiscountEditSuccess"
    />
    <!-- 减免审批弹窗（通过可选理由 / 驳回必填理由） -->
    <DiscountApprovalModal
      v-model:visible="approvalModalVisible"
      :invoice-id="approvalInvoiceId"
      :mode="approvalMode"
      @success="handleApprovalSuccess"
    />
    <!-- 导入弹窗 -->
    <ImportModal
      v-model:visible="importModalVisible"
      title="批量导入结算单"
      :import-api="importInvoices"
      :template-api="downloadInvoiceTemplate"
      template-file-name="结算单导入模板.xlsx"
      @success="loadInvoices"
    />

    <!-- 明细文件生成状态抽屉 -->
    <DetailGenStatusDrawer v-model:visible="detailStatusVisible" @regenerated="loadInvoices" />

    <!-- 批量下载明细文件弹窗 -->
    <BatchDownloadDetailModal v-model:visible="batchDownloadVisible" :ids="selectedInvoiceIds" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import PageHeader from '@/components/PageHeader.vue'
import DataTable, { type DataTableColumn } from '@/components/DataTable.vue'
import { useUserStore } from '@/stores/user'
import { useInvoice } from '@/composables/useInvoice'
import { formatCurrency, formatDate, formatDateTime } from '@/utils/formatters'
import {
  type Invoice,
  exportInvoices,
  importInvoices,
  downloadInvoiceTemplate,
  regenerateInvoiceDetail,
} from '@/api/billing'
import InvoiceFilters from './components/InvoiceFilters.vue'
import ImportModal from './components/ImportModal.vue'
import InvoiceDetailDrawer from './components/InvoiceDetailDrawer.vue'
import DetailGenStatusDrawer from './components/DetailGenStatusDrawer.vue'
import BatchDownloadDetailModal from './components/BatchDownloadDetailModal.vue'
import GenerateInvoiceModal from './components/GenerateInvoiceModal.vue'
import SubmitModal from './components/SubmitModal.vue'
import DiscountEditModal from './components/DiscountEditModal.vue'
import DiscountApprovalModal from './components/DiscountApprovalModal.vue'
import InvoiceStatusBadge from '@/components/invoice/InvoiceStatusBadge.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const can = (p: string) => userStore.hasPermission(p)

// ===== 经理身份校验（用于列表快捷按钮禁用判断）=====
// 超级管理员若非该客户指定经理，同样不可操作（与后端校验保持一致）
const currentUserId = computed(() => userStore.userInfo?.id)

// 是否可点击「运营经理确认」
const canConfirmOps = (record: Invoice) => {
  return currentUserId.value === record.customer_manager_id
}
// 是否可点击「销售经理确认」
const canConfirmSales = (record: Invoice) => {
  return currentUserId.value === record.customer_sales_manager_id
}
// 禁用时的提示文案
const opsDisabledTip = (record: Invoice) =>
  !record.customer_manager_id
    ? '该客户尚未指定运营经理，无法确认'
    : '您不是该客户指定的运营经理，无法确认'
const salesDisabledTip = (record: Invoice) =>
  !record.customer_sales_manager_id
    ? '该客户尚未指定销售经理，无法确认'
    : '您不是该客户指定的销售经理，无法确认'

const {
  loading,
  invoices,
  total,
  currentDetail,
  filters,
  pagination,
  loadInvoices,
  handlePageChange,
  handlePageSizeChange,
  handleSortChange,
  handleSearch,
  handleReset,
  fetchDetail,
  startPolling,
  doSubmit,
  doConfirm,
  doConfirmOps,
  doConfirmSales,
  doRetryDeduction,
  doCancel,
  doDelete,
  doUpdateSettlementAccount,
  selectedInvoiceIds,
  hasSelected,
  handleBatchSelect,
  handleBatchSelectAll,
  clearSelection,
  doBatchSubmit,
  doBatchCancel,
  doBatchDelete,
} = useInvoice()

const drawerVisible = ref(false)
const detailStatusVisible = ref(false)
const batchDownloadVisible = ref(false)
const generateModalVisible = ref(false)
const importModalVisible = ref(false)
const submitModalVisible = ref(false)
const discountEditVisible = ref(false)
const selectedInvoiceId = ref<number>(0)
const retryingId = ref<number | null>(null)

// --- 列定义（含操作列固定右侧） ---
const STORAGE_KEY = 'invoices_table_columns'

interface ColumnDef {
  key: string
  title: string
  width?: number
  align?: 'left' | 'center' | 'right'
  sortable?: boolean
}

const columnDefs: ColumnDef[] = [
  { key: 'invoice_no', title: '结算单号', width: 214, sortable: true },
  { key: 'customer', title: '客户' },
  { key: 'period', title: '周期', width: 190 },
  { key: 'total_amount', title: '总金额', width: 104, align: 'right', sortable: true },
  { key: 'discount_amount', title: '减免金额', width: 76, align: 'right' },
  { key: 'final_amount', title: '最终结算金额', width: 110, align: 'right', sortable: true },
  { key: 'detail_file', title: '文件', width: 56, align: 'center' },
  { key: 'status', title: '状态', width: 78 },
  { key: 'created_at', title: '创建时间', width: 158, sortable: true },
]

const tableColumns = computed<DataTableColumn[]>(() => [
  ...columnDefs.map((col) => ({
    key: col.key,
    title: col.title,
    width: col.width,
    align: col.align,
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

// --- 排序：a-table 三态；清除时 emit 空字符串以便 useInvoice 清除排序状态 ---
const onSorterChange = (dataIndex: string, direction: string) => {
  const dir = direction === 'ascend' || direction === 'descend' ? direction : ''
  handleSortChange(dir ? dataIndex : '', dir)
}

// --- 分页 ---
const onPageChange = (page: number) => {
  handlePageChange(page)
}

const onPageSizeChange = (size: number) => {
  handlePageSizeChange(size)
}

// --- 多选（跨页保留选中） ---
const rowSelectionConfig = computed(() => ({
  type: 'checkbox' as const,
  showCheckedAll: true,
  onlyCurrent: false,
  selectedRowKeys: selectedInvoiceIds.value,
}))

const onRowSelect = (rowKeys: unknown[], _rowKey: unknown, record: unknown) => {
  // arco select 回调签名：(rowKeys, rowKey, record)；转为原 (checked, id)
  const id = (record as Invoice).id
  handleBatchSelect((rowKeys as number[]).includes(id), id)
}

const onSelectAll = (checked: boolean) => {
  handleBatchSelectAll(checked, invoices.value)
}

// --- 行点击进详情（原 <tr @click>） ---
const onRowClick = (record: unknown) => {
  viewInvoice(record as Invoice)
}

const onBatchSubmit = () => {
  Modal.confirm({
    title: '确认批量提交',
    content: `确定要提交所选的 ${selectedInvoiceIds.value.length} 个结算单吗？非草稿状态的结算单将被跳过。`,
    onOk: async () => {
      try {
        await doBatchSubmit()
      } catch {
        // 错误消息已由 useInvoice 处理
      }
    },
  })
}

const onBatchCancel = () => {
  Modal.confirm({
    title: '确认批量取消',
    content: `确定要取消所选的 ${selectedInvoiceIds.value.length} 个结算单吗？不可取消的状态将被跳过。`,
    onOk: async () => {
      try {
        await doBatchCancel()
      } catch {
        // 错误消息已由 useInvoice 处理
      }
    },
  })
}

const onBatchDelete = () => {
  Modal.confirm({
    title: '确认批量删除',
    content: `确定要删除所选的 ${selectedInvoiceIds.value.length} 个结算单吗？此操作不可恢复。`,
    onOk: async () => {
      try {
        await doBatchDelete()
      } catch {
        // 错误消息已由 useInvoice 处理
      }
    },
  })
}

const onBatchDownloadDetail = () => {
  batchDownloadVisible.value = true
}

// --- 操作 ---
const viewInvoice = async (record: Invoice) => {
  selectedInvoiceId.value = record.id
  await fetchDetail(record.id)
  drawerVisible.value = true
  // 如果详情中文件处于生成中，启动轮询
  if (currentDetail.value?.detail_file_status === 'generating') {
    startPolling()
  }
}

const handleRegenerateDetail = async (id: number) => {
  // 重置状态为 pending 并触发异步生成（后端返回即已入队）
  await regenerateInvoiceDetail(id)
  // 刷新详情获取最新状态
  await fetchDetail(id)
  // 启动轮询
  startPolling()
  // 同时刷新列表
  loadInvoices()
}

// 修改结算单结算账户（代扣余额）；composable 内部已刷新详情与列表
const handleUpdateSettlementAccount = async (invoiceId: number, accountId: number | null) => {
  try {
    await doUpdateSettlementAccount(invoiceId, accountId)
  } catch {
    // 错误消息已由 axios 拦截器 / handleError 统一处理
  }
}

const goToCustomer = (id: number) => router.push(`/customers/${id}`)

const exporting = ref(false)
const handleExport = async () => {
  exporting.value = true
  try {
    const params: Record<string, unknown> = {}
    if (filters.status) params.status = filters.status
    const res = await exportInvoices(params)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    const statusPart = filters.status ? `_${filters.status}` : ''
    link.download = `结算单${statusPart}_${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
  } catch {
    Message.error('导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

const handleGenerateSuccess = () => {
  generateModalVisible.value = false
  loadInvoices()
}

const handleSubmitSuccess = async () => {
  submitModalVisible.value = false
  loadInvoices()
  // 如果详情抽屉打开，刷新详情数据
  if (drawerVisible.value && currentDetail.value) {
    await fetchDetail(currentDetail.value.id)
  }
}

const handleDiscountEditSuccess = async () => {
  discountEditVisible.value = false
  loadInvoices()
  if (drawerVisible.value && currentDetail.value) {
    await fetchDetail(currentDetail.value.id)
  }
}

const openDiscountEditModal = (record: Invoice) => {
  selectedInvoiceId.value = record.id
  discountEditVisible.value = true
}

// ===== 减免审批弹窗 =====
const approvalModalVisible = ref(false)
const approvalMode = ref<'approve' | 'reject'>('approve')
const approvalInvoiceId = ref<number>(0)

const openApprovalModal = (record: Invoice, mode: 'approve' | 'reject') => {
  approvalMode.value = mode
  approvalInvoiceId.value = record.id
  approvalModalVisible.value = true
}

const handleApprovalSuccess = async () => {
  approvalModalVisible.value = false
  loadInvoices()
  if (drawerVisible.value && currentDetail.value) {
    await fetchDetail(currentDetail.value.id)
  }
}

const openSubmitModal = (record: Invoice) => {
  selectedInvoiceId.value = record.id
  submitModalVisible.value = true
}

const handleSingleAction = async (
  record: Invoice,
  action:
    | 'submit'
    | 'confirm-ops'
    | 'confirm-sales'
    | 'approve-discount'
    | 'reject-discount'
    | 'confirm'
    | 'retry-deduction'
    | 'cancel'
    | 'delete'
) => {
  const refreshDetailIfOpen = async () => {
    // 如果抽屉打开，刷新详情以反映最新状态
    if (drawerVisible.value && record.id) {
      await fetchDetail(record.id)
    }
  }

  const actions: Record<string, () => Promise<void> | void> = {
    submit: async () => {
      await doSubmit(record.id)
      await refreshDetailIfOpen()
    },
    'confirm-ops': async () => {
      await doConfirmOps(record.id)
      await refreshDetailIfOpen()
    },
    'confirm-sales': async () => {
      await doConfirmSales(record.id)
      await refreshDetailIfOpen()
    },
    'approve-discount': () => {
      openApprovalModal(record, 'approve')
    },
    'reject-discount': () => {
      openApprovalModal(record, 'reject')
    },
    confirm: async () => {
      await doConfirm(record.id)
      await refreshDetailIfOpen()
    },
    'retry-deduction': () => {
      Modal.confirm({
        title: '确认重试扣款',
        content: `确定要对结算单「${record.invoice_no}」重新执行扣款吗？将扣除金额 ${formatCurrency(record.final_amount)}。`,
        onOk: async () => {
          retryingId.value = record.id
          try {
            await doRetryDeduction(record.id)
            await refreshDetailIfOpen()
          } catch {
            // 错误消息已由 useInvoice 或 axios 拦截器处理
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
    // 各 action 内部已有错误处理（useInvoice 的 Message.error 或此处 catch）
    // 此处 catch 防止未处理的 Promise 拒绝
  })
}

// 初始化
loadInvoices()

// 支持 URL query highlight 参数自动打开结算单详情
onMounted(async () => {
  const highlightId = route.query.highlight
  if (highlightId) {
    const id = Number(highlightId)
    if (id > 0) {
      selectedInvoiceId.value = id
      await fetchDetail(id)
      drawerVisible.value = true
    }
  }
})
</script>

<style scoped>
.invoice-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 1440px;
  margin: 0 auto;
}

/* 覆盖 PageHeader 的 margin-bottom，使用 gap 控制间距 */
.invoice-page :deep(.page-header) {
  margin-bottom: 0;
}

/* 按钮样式 */
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

/* 批量操作工具栏 */
.batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  margin-bottom: 12px;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  background: #eff6ff;
}
.batch-toolbar .batch-info {
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
}
.batch-toolbar .batch-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.batch-toolbar .btn-danger-sm {
  color: var(--red);
  border-color: #fecaca;
}
.batch-toolbar .btn-danger-sm:hover {
  background: #fef2f2;
  border-color: #fca5a5;
}
.batch-toolbar-btn {
  margin-left: 6px;
  padding: 2px 8px;
  font-size: 12px;
  border-radius: 8px;
}
/* 结算单号 */
.invoice-no {
  font-variant-numeric: tabular-nums;
  color: var(--ink);
  font-weight: 600;
  font-size: 13px;
  /* 单行显示：tabular-nums 下字符宽度不稳定，禁止换行避免折成两行 */
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
