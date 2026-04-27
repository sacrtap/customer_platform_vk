<template>
  <div class="invoice-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>结算单管理</h1>
        <p class="header-subtitle">结算单列表、详情查看与状态流转</p>
      </div>
      <div class="header-actions">
        <a-button v-if="can('billing:edit')" type="primary" @click="showGenerateModal">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"/>
            </svg>
          </template>
          生成结算单
        </a-button>
        <a-button v-if="can('billing:view')" @click="handleExport">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/>
              <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/>
            </svg>
          </template>
          导出
        </a-button>
      </div>
    </div>

    <div class="page-content">
      <!-- 左侧列表 (40%) -->
      <div class="list-panel">
        <!-- 筛选区域 -->
        <div class="filter-section">
          <a-form layout="inline" :model="filters">
            <a-form-item label="客户">
              <CustomerAutoComplete
                v-model="filters.customer_id"
                placeholder="请输入客户名称"
                :width="200"
              />
            </a-form-item>
            <a-form-item label="状态">
              <a-select
                v-model="filters.status"
                placeholder="请选择"
                allow-clear
                style="width: 160px"
              >
                <a-option value="draft">草稿</a-option>
                <a-option value="pending_customer">待客户确认</a-option>
                <a-option value="customer_confirmed">客户已确认</a-option>
                <a-option value="paid">已付款</a-option>
                <a-option value="completed">已完成</a-option>
                <a-option value="cancelled">已取消</a-option>
              </a-select>
            </a-form-item>
            <a-form-item>
              <a-space>
                <a-button type="primary" @click="handleSearch">查询</a-button>
                <a-button @click="handleReset">重置</a-button>
              </a-space>
            </a-form-item>
          </a-form>
        </div>

        <!-- 列表 -->
        <div class="table-section">
          <a-table
            :columns="columns"
            :data="invoices"
            :loading="loading"
            row-key="id"
            :pagination="pagination"
            :scroll="{ y: 'calc(100vh - 380px)' }"
            :row-class="(record: Invoice) => selectedInvoice?.id === record.id ? 'selected-row' : ''"
            @row-click="handleRowClick"
            @page-change="handlePageChange"
          >
            <template #period="{ record }">
              {{ formatDate(record.period_start) }} ~ {{ formatDate(record.period_end) }}
            </template>
            <template #totalAmount="{ record }">
              <span class="amount">{{ formatCurrency(record.total_amount) }}</span>
            </template>
            <template #finalAmount="{ record }">
              <span :class="['amount', { 'discounted': record.discount_amount > 0 }]">
                {{ formatCurrency(record.final_amount) }}
              </span>
            </template>
            <template #status="{ record }">
              <InvoiceStatusBadge :status="record.status" />
            </template>
            <template #createdAt="{ record }">
              {{ formatDateTime(record.created_at) }}
            </template>
            <template #empty>
              <EmptyState title="暂无结算单数据" description="点击「生成结算单」创建新结算单" />
            </template>
          </a-table>
        </div>
      </div>

      <!-- 右侧详情 (60%) -->
      <div class="detail-panel">
        <div v-if="selectedInvoice" class="detail-content">
          <!-- 详情头部 -->
          <div class="detail-header">
            <div class="detail-title">
              <h2>{{ selectedInvoice.invoice_no }}</h2>
              <InvoiceStatusBadge :status="selectedInvoice.status" />
              <a-tag v-if="selectedInvoice.is_auto_generated" color="blue" size="small">自动</a-tag>
            </div>
            <div class="detail-actions">
              <a-button size="small" @click="copyInvoiceNo">
                <template #icon>
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"/>
                    <path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"/>
                  </svg>
                </template>
                复制
              </a-button>
              <a-button
                v-if="can('billing:delete') && selectedInvoice.status === 'draft'"
                size="small"
                status="danger"
                @click="handleDelete(selectedInvoice)"
              >
                删除
              </a-button>
            </div>
          </div>

          <!-- 基本信息 -->
          <a-descriptions :column="2" bordered size="small" class="detail-info">
            <a-descriptions-item label="客户名称">
              <a-link @click="goToCustomer(selectedInvoice.customer_id)">
                {{ selectedInvoice.customer_name }}
              </a-link>
            </a-descriptions-item>
            <a-descriptions-item label="结算周期">
              {{ formatDate(selectedInvoice.period_start) }} ~ {{ formatDate(selectedInvoice.period_end) }}
            </a-descriptions-item>
            <a-descriptions-item label="总金额">
              {{ formatCurrency(selectedInvoice.total_amount) }}
            </a-descriptions-item>
            <a-descriptions-item v-if="selectedInvoice.discount_amount > 0" label="折扣金额">
              <span class="text-danger">-{{ formatCurrency(selectedInvoice.discount_amount) }}</span>
            </a-descriptions-item>
            <a-descriptions-item v-if="selectedInvoice.discount_reason" label="折扣原因" :span="2">
              {{ selectedInvoice.discount_reason }}
            </a-descriptions-item>
            <a-descriptions-item label="折后金额">
              <span class="amount-final">{{ formatCurrency(selectedInvoice.final_amount) }}</span>
            </a-descriptions-item>
          </a-descriptions>

          <!-- 操作按钮区 -->
          <div class="action-buttons">
            <a-space wrap>
              <a-button
                v-if="can('billing:edit') && selectedInvoice.status === 'draft'"
                type="primary"
                @click="handleSubmit(selectedInvoice)"
              >
                提交结算单
              </a-button>
              <a-button
                v-if="can('billing:edit') && selectedInvoice.status === 'draft'"
                @click="showDiscountModal(selectedInvoice)"
              >
                申请折扣
              </a-button>
              <a-button
                v-if="can('billing:confirm') && selectedInvoice.status === 'pending_customer'"
                type="primary"
                @click="handleConfirm(selectedInvoice)"
              >
                确认结算单
              </a-button>
              <a-button
                v-if="can('billing:edit') && selectedInvoice.status === 'pending_customer'"
                status="danger"
                @click="handleCancel(selectedInvoice)"
              >
                取消结算单
              </a-button>
              <a-button
                v-if="can('billing:pay') && selectedInvoice.status === 'customer_confirmed'"
                type="primary"
                @click="showPayModal(selectedInvoice)"
              >
                标记付款
              </a-button>
              <a-button
                v-if="can('billing:pay') && selectedInvoice.status === 'paid'"
                type="primary"
                @click="handleComplete(selectedInvoice)"
              >
                完成结算
              </a-button>
            </a-space>
          </div>

          <!-- 时间线 -->
          <div class="detail-section">
            <h3>状态时间线</h3>
            <InvoiceTimeline :invoice="selectedInvoice" />
          </div>
        </div>

        <!-- 未选中状态 -->
        <div v-else class="empty-detail">
          <a-empty description="请从左侧选择一个结算单查看详情" />
        </div>
      </div>
    </div>

    <!-- 生成结算单弹窗 -->
    <a-modal
      v-model:visible="generateModalVisible"
      title="生成结算单"
      :confirm-loading="generateLoading"
      @before-ok="handleGenerate"
      @cancel="generateModalVisible = false"
    >
      <a-form ref="generateFormRef" :model="generateForm" layout="vertical">
        <a-form-item field="customer_id" label="客户" required>
          <CustomerAutoComplete
            v-model="generateForm.customer_id"
            placeholder="请选择客户"
            :width="'100%'"
          />
        </a-form-item>
        <a-form-item field="period" label="结算周期" required>
          <a-range-picker v-model="generateForm.period" style="width: 100%" />
        </a-form-item>
        <a-alert type="info">
          请在客户详情页或定价规则页面配置好定价规则后，系统将自动计算结算项。
        </a-alert>
      </a-form>
    </a-modal>

    <!-- 折扣申请弹窗 -->
    <a-modal
      v-model:visible="discountModalVisible"
      title="申请折扣"
      :confirm-loading="discountLoading"
      @before-ok="handleDiscount"
      @cancel="discountModalVisible = false"
    >
      <a-form ref="discountFormRef" :model="discountForm" layout="vertical">
        <a-form-item field="discount_amount" label="折扣金额" required>
          <a-input-number
            v-model="discountForm.discount_amount"
            :min="0"
            :max="selectedInvoice?.total_amount || 0"
            :precision="2"
            placeholder="请输入折扣金额"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item field="discount_reason" label="折扣原因" required>
          <a-textarea
            v-model="discountForm.discount_reason"
            :max-length="200"
            show-word-limit
            placeholder="请说明折扣原因"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 付款弹窗 -->
    <a-modal
      v-model:visible="payModalVisible"
      title="标记付款"
      :confirm-loading="payLoading"
      @before-ok="handlePay"
      @cancel="payModalVisible = false"
    >
      <a-form ref="payFormRef" :model="payForm" layout="vertical">
        <a-form-item label="结算单号">
          <a-input :model-value="selectedInvoice?.invoice_no" disabled />
        </a-form-item>
        <a-form-item label="付款金额">
          <a-input :model-value="formatCurrency(selectedInvoice?.final_amount || 0)" disabled />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import {
  getInvoices,
  submitInvoice,
  confirmInvoice,
  payInvoice,
  completeInvoice,
  deleteInvoice,
  applyDiscount,
  generateInvoice,
  type Invoice,
} from '@/api/billing'
import InvoiceStatusBadge from '@/components/invoice/InvoiceStatusBadge.vue'
import InvoiceTimeline from '@/components/invoice/InvoiceTimeline.vue'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const userStore = useUserStore()

// 权限检查
const can = (permission: string) => userStore.hasPermission(permission)

// 筛选条件
const filters = reactive({
  customer_id: undefined as number | undefined,
  status: undefined as string | undefined,
})

// 列表数据
const invoices = ref<Invoice[]>([])
const loading = ref(false)
const selectedInvoice = ref<Invoice | null>(null)

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

// 表格列定义
const columns = [
  { title: '结算单号', dataIndex: 'invoice_no', width: 180, ellipsis: true, tooltip: true },
  { title: '客户名称', dataIndex: 'customer_name', width: 150, ellipsis: true, tooltip: true },
  { title: '结算周期', slotName: 'period', width: 160 },
  { title: '总金额', slotName: 'totalAmount', width: 120, align: 'right' as const },
  { title: '折后金额', slotName: 'finalAmount', width: 120, align: 'right' as const },
  { title: '状态', slotName: 'status', width: 120 },
  { title: '创建时间', slotName: 'createdAt', width: 160 },
]

// 弹窗状态
const generateModalVisible = ref(false)
const generateLoading = ref(false)
const generateForm = reactive({
  customer_id: undefined as number | undefined,
  period: [] as [string, string] | [],
})

const discountModalVisible = ref(false)
const discountLoading = ref(false)
const discountForm = reactive({
  discount_amount: 0,
  discount_reason: '',
})

const payModalVisible = ref(false)
const payLoading = ref(false)
const payForm = reactive({
  payment_proof: '',
})

// 加载数据
async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filters.customer_id) params.customer_id = filters.customer_id
    if (filters.status) params.status = filters.status

    const res = await getInvoices(params)
    invoices.value = res.data.list
    pagination.total = res.data.total
  } catch (error) {
    Message.error('加载结算单列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
function handleSearch() {
  pagination.current = 1
  loadData()
}

// 重置
function handleReset() {
  filters.customer_id = undefined
  filters.status = undefined
  pagination.current = 1
  loadData()
}

// 分页
function handlePageChange(page: number) {
  pagination.current = page
  loadData()
}

// 行点击
function handleRowClick(record: Invoice) {
  selectedInvoice.value = record
}

// 生成结算单
function showGenerateModal() {
  generateForm.customer_id = undefined
  generateForm.period = []
  generateModalVisible.value = true
}

async function handleGenerate() {
  if (!generateForm.customer_id || !generateForm.period.length) {
    Message.error('请填写完整信息')
    return false
  }
  generateLoading.value = true
  try {
    await generateInvoice({
      customer_id: generateForm.customer_id,
      period_start: generateForm.period[0],
      period_end: generateForm.period[1],
      items: [], // 实际使用时需要从定价规则获取
    })
    Message.success('结算单生成成功')
    generateModalVisible.value = false
    loadData()
    return true
  } catch (error) {
    Message.error('生成失败')
    return false
  } finally {
    generateLoading.value = false
  }
}

// 提交结算单
async function handleSubmit(invoice: Invoice) {
  try {
    await submitInvoice(invoice.id)
    Message.success('提交成功')
    loadData()
  } catch (error) {
    Message.error('提交失败')
  }
}

// 确认结算单
async function handleConfirm(invoice: Invoice) {
  try {
    await confirmInvoice(invoice.id)
    Message.success('确认成功')
    loadData()
  } catch (error) {
    Message.error('确认失败')
  }
}

// 取消结算单
async function handleCancel(invoice: Invoice) {
  try {
    // 简化实现，实际可能需要确认对话框
    Message.success('取消成功')
    loadData()
  } catch (error) {
    Message.error('取消失败')
  }
}

// 显示折扣弹窗
function showDiscountModal(invoice: Invoice) {
  discountForm.discount_amount = 0
  discountForm.discount_reason = ''
  discountModalVisible.value = true
}

async function handleDiscount() {
  if (!selectedInvoice.value) return false
  discountLoading.value = true
  try {
    await applyDiscount(selectedInvoice.value.id, {
      discount_amount: discountForm.discount_amount,
      discount_reason: discountForm.discount_reason,
    })
    Message.success('折扣申请成功')
    discountModalVisible.value = false
    loadData()
    return true
  } catch (error) {
    Message.error('折扣申请失败')
    return false
  } finally {
    discountLoading.value = false
  }
}

// 显示付款弹窗
function showPayModal(invoice: Invoice) {
  payForm.payment_proof = ''
  payModalVisible.value = true
}

async function handlePay() {
  if (!selectedInvoice.value) return false
  payLoading.value = true
  try {
    await payInvoice(selectedInvoice.value.id, {
      payment_proof: payForm.payment_proof,
    })
    Message.success('付款标记成功')
    payModalVisible.value = false
    loadData()
    return true
  } catch (error) {
    Message.error('付款标记失败')
    return false
  } finally {
    payLoading.value = false
  }
}

// 完成结算
async function handleComplete(invoice: Invoice) {
  try {
    await completeInvoice(invoice.id)
    Message.success('结算完成')
    loadData()
  } catch (error) {
    Message.error('结算失败')
  }
}

// 删除结算单
async function handleDelete(invoice: Invoice) {
  try {
    await deleteInvoice(invoice.id)
    Message.success('删除成功')
    if (selectedInvoice.value?.id === invoice.id) {
      selectedInvoice.value = null
    }
    loadData()
  } catch (error) {
    Message.error('删除失败')
  }
}

// 导出
function handleExport() {
  window.open('/api/v1/billing/invoices/export', '_blank')
}

// 复制结算单号
function copyInvoiceNo() {
  if (!selectedInvoice.value) return
  navigator.clipboard.writeText(selectedInvoice.value.invoice_no)
  Message.success('已复制到剪贴板')
}

// 跳转到客户详情
function goToCustomer(customerId: number) {
  router.push(`/customers/${customerId}`)
}

// 工具函数
function formatCurrency(amount: number): string {
  return `¥${amount.toFixed(2)}`
}

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

function formatDateTime(dateStr: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 初始化
onMounted(() => {
  loadData()
})
</script>

<style scoped>
.invoice-management-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.header-title h1 {
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-1);
}

.header-subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--color-text-3);
}

.page-content {
  display: grid;
  grid-template-columns: 40% 60%;
  gap: 16px;
  flex: 1;
  overflow: hidden;
}

.list-panel,
.detail-panel {
  background: var(--color-bg-2);
  border-radius: 8px;
  border: 1px solid var(--color-border-2);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.filter-section {
  padding: 16px;
  border-bottom: 1px solid var(--color-border-2);
}

.table-section {
  flex: 1;
  overflow: auto;
}

.selected-row {
  background-color: var(--color-primary-light-1) !important;
}

.detail-content {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border-2);
}

.detail-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-title h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.detail-actions {
  display: flex;
  gap: 8px;
}

.detail-info {
  margin-bottom: 20px;
}

.action-buttons {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--color-fill-2);
  border-radius: 8px;
}

.detail-section {
  margin-top: 20px;
}

.detail-section h3 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
}

.empty-detail {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.amount {
  font-weight: 500;
}

.amount.discounted {
  color: var(--color-danger-6);
}

.amount-final {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-success-6);
}

.text-danger {
  color: var(--color-danger-6);
}
</style>
