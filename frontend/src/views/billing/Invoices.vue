<template>
  <div class="invoice-management-page">
    <!-- Page Header -->
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

    <!-- 筛选区域 -->
    <div class="filter-section">
      <a-form layout="vertical" :model="filters">
        <a-row :gutter="16">
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="客户">
              <CustomerAutoComplete
                v-model="filters.customer_id"
                placeholder="请输入客户名称"
                :width="'100%'"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="状态">
              <a-select
                v-model="filters.status"
                placeholder="请选择"
                allow-clear
                style="width: 100%"
              >
                <a-option value="draft">草稿</a-option>
                <a-option value="pending_customer">待客户确认</a-option>
                <a-option value="customer_confirmed">客户已确认</a-option>
                <a-option value="paid">已付款</a-option>
                <a-option value="completed">已完成</a-option>
                <a-option value="cancelled">已取消</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="&nbsp;">
              <a-space>
                <a-button type="primary" @click="handleSearch">查询</a-button>
                <a-button @click="handleReset">重置</a-button>
              </a-space>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </div>

    <!-- 表格 -->
    <div class="table-section">
      <a-table
        :columns="columns"
        :data="invoices"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        :scroll="{ x: 'max-content' }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @sorter-change="handleSort"
      >
        <template #period="{ record }">
          {{ formatDate(record.period_start) }} ~ {{ formatDate(record.period_end) }}
        </template>
        <template #totalAmount="{ record }">
          <span class="amount">{{ formatCurrency(record.total_amount) }}</span>
        </template>
        <template #discount="{ record }">
          <span v-if="record.discount_amount && record.discount_amount > 0" class="amount text-danger">
            -{{ formatCurrency(record.discount_amount) }}
          </span>
          <span v-else class="text-muted">-</span>
        </template>
        <template #finalAmount="{ record }">
          <span class="amount-final">{{ formatCurrency(record.final_amount) }}</span>
        </template>
        <template #status="{ record }">
          <InvoiceStatusBadge :status="record.status" />
        </template>
        <template #createdAt="{ record }">
          {{ formatDateTime(record.created_at) }}
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button type="primary" size="small" @click="viewInvoice(record)">查看</a-button>
            <a-button 
              v-if="record.status === 'draft'" 
              type="primary" 
              size="small" 
              @click="handleSubmit(record)"
            >
              提交
            </a-button>
            <a-dropdown>
              <a-button type="text" size="small">更多</a-button>
              <template #content>
                <a-doption 
                  v-if="record.status === 'draft' && can('billing:edit') && record.total_amount > 0" 
                  @click="showDiscountModal(record)"
                >
                  申请折扣
                </a-doption>
                <a-doption 
                  v-if="record.status === 'pending_customer' && can('billing:confirm')" 
                  @click="handleConfirm(record)"
                >
                  确认结算单
                </a-doption>
                <a-doption 
                  v-if="record.status === 'pending_customer' && can('billing:edit')" 
                  style="color: #ff4d4f" 
                  @click="handleCancel(record)"
                >
                  取消结算单
                </a-doption>
                <a-doption 
                  v-if="record.status === 'customer_confirmed' && can('billing:pay')" 
                  @click="showPayModal(record)"
                >
                  标记付款
                </a-doption>
                <a-doption 
                  v-if="record.status === 'paid' && can('billing:pay')" 
                  @click="handleComplete(record)"
                >
                  完成结算
                </a-doption>
                <a-doption 
                  v-if="record.status === 'draft' && can('billing:delete')" 
                  style="color: #ff4d4f" 
                  @click="handleDelete(record)"
                >
                  删除
                </a-doption>
                <a-doption @click="handleExportSingle(record)">
                  导出结算单
                </a-doption>
              </template>
            </a-dropdown>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无结算单数据" description="点击「生成结算单」创建新结算单" />
        </template>
      </a-table>
    </div>

    <!-- 结算单详情 Drawer -->
    <a-drawer
      v-model:visible="drawerVisible"
      title="结算单详情"
      width="720px"
      unmount-on-close
    >
      <template v-if="selectedInvoice">
        <div class="drawer-content">
          <!-- 详情头部 -->
          <div class="detail-header">
            <div class="detail-title">
              <h2>{{ selectedInvoice.invoice_no }}</h2>
              <InvoiceStatusBadge :status="selectedInvoice.status" />
              <a-tag v-if="selectedInvoice.is_auto_generated" color="blue" size="small">自动</a-tag>
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
            <a-descriptions-item v-if="selectedInvoice.discount_amount && selectedInvoice.discount_amount > 0" label="折扣金额">
              <span class="text-danger">-{{ formatCurrency(selectedInvoice.discount_amount) }}</span>
            </a-descriptions-item>
            <a-descriptions-item v-if="selectedInvoice.discount_reason" label="折扣原因" :span="2">
              {{ selectedInvoice.discount_reason }}
            </a-descriptions-item>
            <a-descriptions-item label="折后金额">
              <span class="amount-final">{{ formatCurrency(selectedInvoice.final_amount) }}</span>
            </a-descriptions-item>
          </a-descriptions>

          <!-- 结算明细 -->
          <div class="detail-section">
            <div class="section-header">
              <h3>结算明细</h3>
              <a-button
                v-if="can('billing:edit') && selectedInvoice.status === 'draft' && (!selectedInvoice.items || selectedInvoice.items.length === 0)"
                type="primary"
                size="small"
                :loading="calculating"
                @click="handleCalculateItems"
              >
                自动生成明细
              </a-button>
            </div>
            <a-table
              :columns="invoiceItemColumns"
              :data="selectedInvoice.items || []"
              :pagination="false"
              size="small"
              row-key="id"
            >
              <template #layer_type="{ record }">
                <a-tag :color="record.layer_type === 'multi' ? 'purple' : 'blue'">
                  {{ record.layer_type === 'multi' ? '多层' : '单层' }}
                </a-tag>
              </template>
              <template #subtotal="{ record }">
                <span class="amount">{{ formatCurrency(record.subtotal || record.quantity * record.unit_price) }}</span>
              </template>
              <template #empty>
                <a-empty description="暂无结算明细，草稿状态下可自动生成" />
              </template>
            </a-table>
          </div>

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
                v-if="can('billing:edit') && selectedInvoice.status === 'draft' && selectedInvoice.total_amount > 0"
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
      </template>
    </a-drawer>

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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import {
  getInvoices,
  getInvoice,
  submitInvoice,
  confirmInvoice,
  payInvoice,
  completeInvoice,
  deleteInvoice,
  applyDiscount,
  generateInvoice,
  calculateInvoiceItems,
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

// Drawer 状态
const drawerVisible = ref(false)

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

// 排序状态
const sortState = reactive({
  sort_by: 'id',
  sort_order: 'ascend' as 'ascend' | 'descend' | '',
})

// 表格列定义
const columns = [
  { title: '结算单号', dataIndex: 'invoice_no', width: 180, sortable: { sortDirections: ['ascend', 'descend'] }, ellipsis: true, tooltip: true },
  { title: '客户名称', dataIndex: 'customer_name', width: 180, sortable: { sortDirections: ['ascend', 'descend'] }, ellipsis: true, tooltip: true },
  { title: '结算周期', slotName: 'period', width: 220, ellipsis: true, tooltip: true },
  { title: '总金额', slotName: 'totalAmount', width: 140, align: 'right' as const, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '折扣', slotName: 'discount', width: 120, align: 'right' as const },
  { title: '折后金额', slotName: 'finalAmount', width: 140, align: 'right' as const, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '状态', slotName: 'status', width: 130 },
  { title: '创建时间', slotName: 'createdAt', width: 180, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '操作', slotName: 'action', width: 180, fixed: 'right' as const },
]

// 处理排序
const handleSort = (dataIndex: string, direction: 'ascend' | 'descend' | '') => {
  if (!direction) {
    sortState.sort_by = 'id'
    sortState.sort_order = 'ascend'
  } else {
    sortState.sort_by = dataIndex
    sortState.sort_order = direction
  }
  pagination.current = 1
  loadData()
}

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
    const params: Record<string, string | number> = {
      page: pagination.current,
      page_size: pagination.pageSize,
      sort_by: sortState.sort_by,
      sort_order: sortState.sort_order === 'ascend' ? 'asc' : sortState.sort_order === 'descend' ? 'desc' : 'asc',
    }
    if (filters.customer_id) params.customer_id = filters.customer_id
    if (filters.status) params.status = filters.status

    const res = await getInvoices(params)
    invoices.value = res.data.list
    pagination.total = res.data.total
  } catch (error) {
    console.error('加载结算单列表失败:', error)
    Message.error('加载结算单列表失败: ' + (error as Error).message)
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

// 每页条数变化
function handlePageSizeChange(pageSize: number) {
  pagination.pageSize = pageSize
  pagination.current = 1
  loadData()
}

// 查看结算单详情
async function viewInvoice(record: Invoice) {
  try {
    const res = await getInvoice(record.id)
    selectedInvoice.value = res.data
    drawerVisible.value = true
  } catch (error) {
    Message.error('加载结算单详情失败')
  }
}

// 结算明细列定义
const invoiceItemColumns = [
  { title: '设备类型', dataIndex: 'device_type', width: 100 },
  { title: '楼层类型', dataIndex: 'layer_type', slotName: 'layer_type', width: 100 },
  { title: '数量', dataIndex: 'quantity', width: 120, align: 'right' as const },
  { title: '单价', dataIndex: 'unit_price', width: 120, align: 'right' as const },
  { title: '小计', slotName: 'subtotal', width: 120, align: 'right' as const },
]

// 自动生成明细
const calculating = ref(false)

async function handleCalculateItems() {
  if (!selectedInvoice.value) return
  calculating.value = true
  try {
    await calculateInvoiceItems({
      customer_id: selectedInvoice.value.customer_id,
      period_start: selectedInvoice.value.period_start,
      period_end: selectedInvoice.value.period_end,
    })
    // 刷新详情
    const detailRes = await getInvoice(selectedInvoice.value.id)
    selectedInvoice.value = detailRes.data
    Message.success('已生成结算明细')
  } catch (error) {
    Message.error('生成明细失败: ' + (error as Error).message)
  } finally {
    calculating.value = false
  }
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
      items: [],
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
  Modal.confirm({
    title: '确认提交',
    content: `确定要提交结算单 ${invoice.invoice_no} 吗？提交后将进入待确认状态。`,
    onOk: async () => {
      try {
        await submitInvoice(invoice.id)
        Message.success('提交成功')
        loadData()
        if (selectedInvoice.value?.id === invoice.id) {
          selectedInvoice.value = invoice
        }
      } catch (error) {
        Message.error('提交失败')
      }
    },
  })
}

// 确认结算单
async function handleConfirm(invoice: Invoice) {
  try {
    await confirmInvoice(invoice.id)
    Message.success('确认成功')
    loadData()
    if (selectedInvoice.value?.id === invoice.id) {
      selectedInvoice.value = invoice
    }
  } catch (error) {
    Message.error('确认失败')
  }
}

// 取消结算单
async function handleCancel(_invoice: Invoice) {
  try {
    Modal.confirm({
      title: '确认取消',
      content: '确定要取消该结算单吗？',
      onOk: async () => {
        Message.success('取消成功')
        loadData()
      },
    })
  } catch (error) {
    Message.error('取消失败')
  }
}

// 显示折扣弹窗
function showDiscountModal(invoice: Invoice) {
  selectedInvoice.value = invoice
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
    if (selectedInvoice.value) {
      // Drawer 中显示折扣信息
      selectedInvoice.value.discount_amount = discountForm.discount_amount
      selectedInvoice.value.discount_reason = discountForm.discount_reason
    }
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
  selectedInvoice.value = invoice
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
    if (selectedInvoice.value?.id === invoice.id) {
      selectedInvoice.value = invoice
    }
  } catch (error) {
    Message.error('结算失败')
  }
}

// 删除结算单
async function handleDelete(invoice: Invoice) {
  try {
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，确定要删除该结算单吗？',
      onOk: async () => {
        await deleteInvoice(invoice.id)
        Message.success('删除成功')
        loadData()
        if (selectedInvoice.value?.id === invoice.id) {
          selectedInvoice.value = null
          drawerVisible.value = false
        }
      },
    })
  } catch (error) {
    Message.error('删除失败')
  }
}

// 导出全部
function handleExport() {
  window.open('/api/v1/billing/invoices/export', '_blank')
}

// 单条导出
function handleExportSingle(_invoice: Invoice) {
  window.open(`/api/v1/billing/invoices/${_invoice.id}/export`, '_blank')
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
  padding: 0;
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-9: #2f3645;
  --neutral-10: #1d2330;
  --primary-6: #0369a1;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-10);
  margin-bottom: 8px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--neutral-6);
}

.header-actions {
  display: flex;
  gap: 12px;
}

/* 筛选区域 */
.filter-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  margin-bottom: 24px;
}

.filter-section .arco-form-item {
  margin-bottom: 0;
}

.filter-section .arco-select,
.filter-section .arco-input {
  width: 100%;
}

/* 表格区域 */
.table-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

:deep(.arco-table) {
  font-size: 14px;
}

:deep(.arco-table th) {
  font-size: 13px;
  white-space: nowrap;
  background: var(--neutral-1);
  color: var(--neutral-6);
  font-weight: 600;
}

:deep(.arco-table td) {
  color: var(--neutral-7);
}

:deep(.arco-table tr:hover td) {
  background: var(--neutral-1);
}

/* Drawer 内容样式 */
.drawer-content {
  padding: 0 4px;
}

.detail-header {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--neutral-2);
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

.detail-info {
  margin-bottom: 20px;
}

.action-buttons {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--neutral-1);
  border-radius: 8px;
}

.detail-section {
  margin-top: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.detail-section h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

/* 金额样式 */
.amount {
  font-weight: 500;
}

.amount-final {
  font-size: 16px;
  font-weight: 600;
  color: var(--primary-6);
}

.text-danger {
  color: #ff4d4f;
}

.text-muted {
  color: var(--neutral-5);
}
</style>
