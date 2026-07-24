<template>
  <div class="invoice-page">
    <!-- PageHeader -->
    <PageHeader eyebrow="Billing" title="结算单管理" subtitle="结算单列表、详情查看与状态流转">
      <template #actions>
        <button v-if="can('billing:view')" class="btn" @click="handleExport">导出</button>
        <button v-if="can('billing:edit')" class="btn primary" @click="generateModalVisible = true">
          生成结算单
        </button>
      </template>
    </PageHeader>

    <!-- 筛选 + 表格 在同一卡片内 -->
    <div class="card pad main-card">
      <!-- 筛选器 -->
      <InvoiceFilters v-model:filters="filters" @search="handleSearch" @reset="handleReset" />

      <!-- 表格 -->
      <div class="table-section">
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th
                  :class="getThClass('invoice_no')"
                  style="width: 200px"
                  @click="toggleSort('invoice_no')"
                >
                  <span>结算单号</span>
                  <span class="th-sort-indicator"></span>
                </th>
                <th style="width: 180px">客户</th>
                <th style="width: 220px">周期</th>
                <th
                  :class="getThClass('total_amount')"
                  style="width: 120px; text-align: right"
                  @click="toggleSort('total_amount')"
                >
                  <span>总金额</span>
                  <span class="th-sort-indicator"></span>
                </th>
                <th style="width: 90px; text-align: right">折扣</th>
                <th
                  :class="getThClass('final_amount')"
                  style="width: 120px; text-align: right"
                  @click="toggleSort('final_amount')"
                >
                  <span>实付</span>
                  <span class="th-sort-indicator"></span>
                </th>
                <th style="width: 100px">状态</th>
                <th
                  :class="getThClass('created_at')"
                  style="width: 150px"
                  @click="toggleSort('created_at')"
                >
                  <span>创建时间</span>
                  <span class="th-sort-indicator"></span>
                </th>
                <th style="width: 180px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="record in invoices"
                :key="record.id"
                class="row-clickable"
                @click="viewInvoice(record)"
              >
                <!-- 结算单号 -->
                <td>
                  <span class="invoice-no">{{ record.invoice_no }}</span>
                </td>
                <!-- 客户 -->
                <td>
                  <span class="cust-name">{{
                    record.customer_name || `#${record.customer_id}`
                  }}</span>
                </td>
                <!-- 周期 -->
                <td>
                  <span class="cell-nowrap"
                    >{{ formatDate(record.period_start) }} ~
                    {{ formatDate(record.period_end) }}</span
                  >
                </td>
                <!-- 总金额 -->
                <td style="text-align: right">
                  <span class="amount">{{ formatCurrency(record.total_amount) }}</span>
                </td>
                <!-- 折扣 -->
                <td style="text-align: right">
                  <span
                    v-if="record.discount_amount && record.discount_amount > 0"
                    class="amount text-danger"
                  >
                    -{{ formatCurrency(record.discount_amount) }}
                  </span>
                  <span v-else class="subtle">-</span>
                </td>
                <!-- 实付 -->
                <td style="text-align: right">
                  <span class="amount-final">{{ formatCurrency(record.final_amount) }}</span>
                </td>
                <!-- 状态 -->
                <td>
                  <InvoiceStatusBadge :status="record.status" />
                </td>
                <!-- 创建时间 -->
                <td>
                  <span class="cell-nowrap">{{ formatDateTime(record.created_at) }}</span>
                </td>
                <!-- 操作 -->
                <td style="white-space: nowrap" @click.stop>
                  <button
                    v-if="record.status === 'draft'"
                    class="btn btn-primary-sm"
                    style="padding: 4px 10px; font-size: 12px"
                    @click="handleSingleAction(record, 'submit')"
                  >
                    提交
                  </button>
                  <button
                    v-if="can('billing:ops_approve') && record.status === 'pending_ops'"
                    class="btn btn-primary-sm"
                    :style="{
                      padding: '4px 10px',
                      fontSize: '12px',
                      marginLeft: '4px',
                      opacity: canConfirmOps(record) ? 1 : 0.5,
                      cursor: canConfirmOps(record) ? 'pointer' : 'not-allowed',
                    }"
                    :disabled="!canConfirmOps(record)"
                    :title="canConfirmOps(record) ? '' : opsDisabledTip(record)"
                    @click="canConfirmOps(record) && handleSingleAction(record, 'confirm-ops')"
                  >
                    运营确认
                  </button>
                  <button
                    v-if="can('billing:sales_approve') && record.status === 'pending_sales'"
                    class="btn btn-primary-sm"
                    :style="{
                      padding: '4px 10px',
                      fontSize: '12px',
                      marginLeft: '4px',
                      opacity: canConfirmSales(record) ? 1 : 0.5,
                      cursor: canConfirmSales(record) ? 'pointer' : 'not-allowed',
                    }"
                    :disabled="!canConfirmSales(record)"
                    :title="canConfirmSales(record) ? '' : salesDisabledTip(record)"
                    @click="canConfirmSales(record) && handleSingleAction(record, 'confirm-sales')"
                  >
                    销售确认
                  </button>
                  <button
                    v-if="record.status === 'pending_customer'"
                    class="btn btn-primary-sm"
                    style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
                    @click="handleSingleAction(record, 'confirm')"
                  >
                    客户确认
                  </button>
                  <button
                    v-if="record.status === 'customer_confirmed'"
                    class="btn btn-primary-sm"
                    style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
                    :disabled="retryingId === record.id"
                    @click="handleSingleAction(record, 'retry-deduction')"
                  >
                    {{ retryingId === record.id ? '扣款中...' : '重试扣款' }}
                  </button>
                  <button
                    v-if="
                      ['draft', 'pending_ops', 'pending_sales', 'pending_customer'].includes(
                        record.status
                      )
                    "
                    class="btn"
                    style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
                    @click="handleSingleAction(record, 'cancel')"
                  >
                    取消
                  </button>
                  <button
                    v-if="can('billing:edit') && record.status === 'draft'"
                    class="btn btn-danger"
                    style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
                    @click="handleSingleAction(record, 'delete')"
                  >
                    删除
                  </button>
                </td>
              </tr>
              <tr v-if="invoices.length === 0 && !loading">
                <td :colspan="9" class="empty-state">暂无结算单数据</td>
              </tr>
              <tr v-if="loading">
                <td :colspan="9" class="loading-state">加载中...</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分页 -->
        <div class="pagination">
          <span class="page-total">共 {{ total.toLocaleString() }} 条</span>
          <div class="pagination-right">
            <span class="page-size">
              每页
              <select
                class="page-size-select"
                :value="pagination.pageSize"
                @change="onPageSizeChange"
              >
                <option v-for="size in pageSizeOptions" :key="size" :value="size">
                  {{ size }}
                </option>
              </select>
              条
            </span>
            <div class="page-controls">
              <button
                class="page-btn"
                :disabled="pagination.current <= 1"
                @click="onPageChange(pagination.current - 1)"
              >
                ‹
              </button>
              <button
                v-for="p in displayPages"
                :key="p"
                class="page-btn"
                :class="{ active: p === pagination.current, ellipsis: p === -1 }"
                :disabled="p === -1"
                @click="p > 0 && onPageChange(p)"
              >
                {{ p === -1 ? '…' : p }}
              </button>
              <button
                class="page-btn"
                :disabled="pagination.current >= totalPages"
                @click="onPageChange(pagination.current + 1)"
              >
                ›
              </button>
            </div>
            <span class="page-jump">
              跳至
              <input
                type="number"
                class="page-jump-input"
                :value="pagination.current"
                :min="1"
                :max="totalPages"
                @keydown.enter="onJumpPage(($event.target as HTMLInputElement).value)"
              />
              页
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 结算单详情抽屉 -->
    <InvoiceDetailDrawer
      v-model:visible="drawerVisible"
      :invoice="currentDetail"
      :retrying="retryingId === currentDetail?.id"
      @go-customer="goToCustomer"
      @submit="handleSingleAction(currentDetail!, 'submit')"
      @confirm-ops="handleSingleAction(currentDetail!, 'confirm-ops')"
      @confirm-sales="handleSingleAction(currentDetail!, 'confirm-sales')"
      @confirm="handleSingleAction(currentDetail!, 'confirm')"
      @retry-deduction="handleSingleAction(currentDetail!, 'retry-deduction')"
      @cancel="handleSingleAction(currentDetail!, 'cancel')"
    />

    <!-- 生成结算单弹窗 -->
    <GenerateInvoiceModal v-model:visible="generateModalVisible" @success="handleGenerateSuccess" />
    <!-- 折扣弹窗 -->
    <DiscountModal
      v-model:visible="discountModalVisible"
      :invoice-id="selectedInvoiceId"
      @success="handleDiscountSuccess"
    />
    <!-- 付款弹窗 -->
    <PayModal
      v-model:visible="payModalVisible"
      :invoice-id="selectedInvoiceId"
      @success="handlePaySuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Modal } from '@arco-design/web-vue'
import PageHeader from '@/components/PageHeader.vue'
import { useUserStore } from '@/stores/user'
import { useInvoice } from '@/composables/useInvoice'
import { formatCurrency, formatDate, formatDateTime } from '@/utils/formatters'
import type { Invoice } from '@/api/billing'
import InvoiceFilters from './components/InvoiceFilters.vue'
import InvoiceDetailDrawer from './components/InvoiceDetailDrawer.vue'
import GenerateInvoiceModal from './components/GenerateInvoiceModal.vue'
import DiscountModal from './components/DiscountModal.vue'
import PayModal from './components/PayModal.vue'
import InvoiceStatusBadge from '@/components/invoice/InvoiceStatusBadge.vue'

const router = useRouter()
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
  doSubmit,
  doConfirm,
  doConfirmOps,
  doConfirmSales,
  doRetryDeduction,
  doCancel,
  doDelete,
} = useInvoice()

const drawerVisible = ref(false)
const generateModalVisible = ref(false)
const discountModalVisible = ref(false)
const payModalVisible = ref(false)
const selectedInvoiceId = ref<number>(0)
const retryingId = ref<number | null>(null)

// --- 排序 ---
const sortKey = ref('')
const sortDir = ref<'asc' | 'desc' | ''>('')

const sortableColumns = ['invoice_no', 'total_amount', 'final_amount', 'created_at']

const getThClass = (key: string) => {
  if (!sortableColumns.includes(key)) return ''
  const classes = ['th-sortable']
  if (sortKey.value === key) {
    if (sortDir.value === 'asc') classes.push('sort-asc')
    else if (sortDir.value === 'desc') classes.push('sort-desc')
  }
  return classes.join(' ')
}

const toggleSort = (key: string) => {
  if (!sortableColumns.includes(key)) return
  if (sortKey.value === key) {
    if (sortDir.value === 'asc') sortDir.value = 'desc'
    else if (sortDir.value === 'desc') {
      sortKey.value = ''
      sortDir.value = ''
    } else sortDir.value = 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
  // 当排序被清除时（第三次点击），sortKey.value 为空字符串，
  // 需要传递空字符串以便 useInvoice 正确清除排序状态
  handleSortChange(sortKey.value, sortDir.value)
}

// --- 分页 ---
const pageSizeOptions = pagination.pageSizeOptions || [10, 20, 50, 100]
const totalPages = computed(() => Math.ceil(total.value / pagination.pageSize) || 1)

const displayPages = computed(() => {
  const current = pagination.current
  const t = totalPages.value
  const pages: number[] = []

  if (t <= 7) {
    for (let i = 1; i <= t; i++) pages.push(i)
  } else {
    pages.push(1)
    if (current > 3) pages.push(-1)
    const start = Math.max(2, current - 1)
    const end = Math.min(t - 1, current + 1)
    for (let i = start; i <= end; i++) pages.push(i)
    if (current < t - 2) pages.push(-1)
    pages.push(t)
  }
  return pages
})

const onPageChange = (page: number) => {
  if (page < 1 || page > totalPages.value) return
  handlePageChange(page)
}

const onPageSizeChange = (e: Event) => {
  handlePageSizeChange(Number((e.target as HTMLSelectElement).value))
}

const onJumpPage = (val: string) => {
  const page = parseInt(val)
  if (page >= 1 && page <= totalPages.value) {
    onPageChange(page)
  }
}

// --- 操作 ---
const viewInvoice = async (record: Invoice) => {
  selectedInvoiceId.value = record.id
  await fetchDetail(record.id)
  drawerVisible.value = true
}

const goToCustomer = (id: number) => router.push(`/customers/${id}`)

const handleExport = () => {}

const handleGenerateSuccess = () => {
  generateModalVisible.value = false
  loadInvoices()
}

const handleDiscountSuccess = () => {
  discountModalVisible.value = false
}

const handlePaySuccess = () => {
  payModalVisible.value = false
}

const handleSingleAction = async (
  record: Invoice,
  action:
    | 'submit'
    | 'confirm-ops'
    | 'confirm-sales'
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
</script>

<style scoped>
.invoice-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px 44px;
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

/* 表格容器 */
.table-section {
  display: flex;
  flex-direction: column;
}
.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 15px;
}

/* 表格 */
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
  position: sticky;
  top: 0;
  z-index: 1;
}
.table tbody tr {
  transition: background 0.15s;
}
.table tbody tr:hover td {
  background: #f8fbff;
}
.table tbody tr.row-clickable {
  cursor: pointer;
}

/* 排序表头 */
.th-sortable {
  cursor: pointer;
  user-select: none;
  position: relative;
  padding-right: 20px !important;
}
.th-sortable:hover {
  color: var(--primary);
}
.th-sort-indicator {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 10px;
  color: var(--muted);
  line-height: 1;
}
.th-sortable.sort-asc .th-sort-indicator,
.th-sortable.sort-desc .th-sort-indicator {
  color: var(--primary);
}
.th-sortable.sort-asc .th-sort-indicator::after {
  content: '▲';
}
.th-sortable.sort-desc .th-sort-indicator::after {
  content: '▼';
}
.th-sortable:not(.sort-asc):not(.sort-desc) .th-sort-indicator::after {
  content: '⇅';
  opacity: 0.4;
}

/* 结算单号 */
.invoice-no {
  font-variant-numeric: tabular-nums;
  color: var(--ink);
  font-weight: 600;
  font-size: 13px;
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
.cell-nowrap {
  white-space: nowrap;
}

/* 空状态 / 加载状态 */
.empty-state,
.loading-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--muted);
  font-size: 14px;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #edf2f7;
}
.page-total {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.pagination-right {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: auto;
}
.page-size {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}
.page-size-select {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 3px 6px;
  font: inherit;
  font-size: 12px;
  color: var(--ink);
  background: #fff;
  cursor: pointer;
}
.page-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}
.page-btn {
  min-width: 32px;
  height: 32px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  border-radius: 8px;
  padding: 0 8px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.page-btn:hover:not(:disabled):not(.active) {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}
.page-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  cursor: default;
}
.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-btn.ellipsis {
  border: none;
  background: transparent;
  cursor: default;
  opacity: 1;
}
.page-jump {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}
.page-jump-input {
  width: 48px;
  height: 30px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0 6px;
  font: inherit;
  font-size: 12px;
  text-align: center;
  color: var(--ink);
  background: #fff;
}
.page-jump-input:focus {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 2px rgba(147, 197, 253, 0.2);
}

@media (max-width: 640px) {
  .pagination {
    justify-content: center;
  }
  .page-size,
  .page-jump {
    display: none;
  }
}
</style>
